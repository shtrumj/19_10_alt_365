#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wbxml_builder.py — Microsoft EAS 14.1-compliant WBXML builders.

Highlights
- AirSync (CP 0), Email (CP 2), AirSyncBase (CP 17) tokens.
- AirSyncBase <Body>: Type -> EstimatedDataSize -> Truncated -> Data.
- DateReceived always ends with 'Z' (UTC).
"""

from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from email import policy
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, formatdate, make_msgid

# WBXML control
SWITCH_PAGE = 0x00
END         = 0x01
STR_I       = 0x03

# Code pages
CP_AIRSYNC     = 0
CP_PING        = 1  # Ping codepage for push notifications
CP_EMAIL       = 2
CP_AIRSYNCBASE = 17
CP_PROVISION   = 14

# AirSync (CP 0)
AS_Sync            = 0x05
AS_Responses       = 0x06
AS_Add             = 0x07
AS_Change          = 0x08
AS_Delete          = 0x09
AS_Fetch           = 0x0A
AS_SyncKey         = 0x0B
AS_ClientId        = 0x0C
AS_ServerId        = 0x0D
AS_Status          = 0x0E
AS_Collection      = 0x0F
AS_Class           = 0x10
AS_CollectionId    = 0x12
AS_GetChanges      = 0x13
AS_MoreAvailable   = 0x14
AS_WindowSize      = 0x15
AS_Commands        = 0x16
AS_Collections     = 0x1C
AS_ApplicationData = 0x1D

# Email (CP 2)
EM_DateReceived   = 0x0F
EM_MessageClass   = 0x13
EM_Subject        = 0x14
EM_Read           = 0x15
EM_To             = 0x16
EM_From           = 0x18
EM_InternetCPID   = 0x39  # UTF-8 = 65001

# AirSyncBase (CP 17)
ASB_Type              = 0x06
ASB_Body              = 0x0A
ASB_Data              = 0x0B
ASB_EstimatedDataSize = 0x0C
ASB_Truncated         = 0x0D
ASB_ContentType       = 0x0E
ASB_NativeBodyType    = 0x16


class WBXMLWriter:
    def __init__(self):
        self.buf = bytearray()
        self.cur_page = 0xFFFF

    def header(self):
        # WBXML v1.3, public id 0x01 (unknown), charset UTF-8 (0x6A), string table = 0
        self.buf.extend([0x03, 0x01, 0x6A, 0x00])

    def write_byte(self, b: int): self.buf.append(b & 0xFF)

    def write_str(self, s: str):
        self.write_byte(STR_I)
        self.buf.extend(s.encode("utf-8"))
        self.write_byte(0x00)

    def page(self, cp: int):
        if self.cur_page != cp:
            self.write_byte(SWITCH_PAGE)
            self.write_byte(cp & 0xFF)
            self.cur_page = cp

    # Alias to match older call sites
    def cp(self, cp: int):
        self.page(cp)

    def start(self, tok: int, with_content: bool = True):
        self.write_byte((tok | 0x40) if with_content else tok)

    def end(self): self.write_byte(END)

    def bytes(self) -> bytes: return bytes(self.buf)


def _ensure_utc_z(dt_or_str: Any) -> str:
    if isinstance(dt_or_str, datetime):
        return dt_or_str.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"
    if isinstance(dt_or_str, str):
        s = dt_or_str
        if not s.endswith("Z"):
            # best-effort: append 'Z' if missing
            if "T" in s:
                # strip fractional if any to keep things tidy
                main = s.split(".")[0]
                return main + ".000Z"
            return s + "Z"
        return s
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000") + "Z"


@dataclass
class SyncBatch:
    response_sync_key: str
    payload: bytes
    sent_count: int
    total_available: int
    more_available: bool


def _select_body_content(em: Dict[str, Any], body_type_preference: int = 2) -> tuple[str, int]:
    """
    Choose body content according to BodyPreference:
    - 2 => HTML preferred (if available), else plain
    - 1 => Plain preferred (if available), else HTML
    Returns (content, native_type), where native_type: 1=Plain, 2=HTML
    """
    html = str(em.get("body_html") or em.get("html") or "")
    plain = str(em.get("body") or em.get("preview") or "")
    if body_type_preference == 1:
        content = plain or html
        native = 1 if plain else 2 if html else 1
    else:
        content = html or plain
        native = 2 if html else 1 if plain else 1
    return content, native


def _truncate_bytes(data: bytes, limit: Optional[int]) -> tuple[bytes, str]:
    if not data:
        return data, "0"
    if limit is None:
        return data, "0"
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        return data, "0"
    if limit_int <= 0 or len(data) <= limit_int:
        return data, "0"
    return data[:limit_int], "1"


def _format_email_date(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "")
        try:
            if text.endswith("Z"):
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(text)
        except Exception:
            dt = datetime.utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _build_mime_message(em: Dict[str, Any], html_body: str, plain_body: str) -> bytes:
    """Build a proper MIME message for ActiveSync body_type 4 responses."""
    msg = MIMEMultipart('alternative')

    subject = str(em.get('subject') or '')
    if subject:
        msg['Subject'] = subject

    from_addr = str(em.get('from') or em.get('sender') or '')
    to_addr = str(em.get('to') or em.get('recipient') or '')
    if from_addr:
        msg['From'] = from_addr
    if to_addr:
        msg['To'] = to_addr

    created_at = em.get('created_at')
    try:
        msg['Date'] = _format_email_date(created_at)
    except Exception:
        msg['Date'] = formatdate(localtime=True)

    msg['Message-ID'] = em.get('message_id') or make_msgid()
    
    # Add MIME-Version header (required for proper MIME parsing)
    msg['MIME-Version'] = '1.0'
    
    # Add Content-Type header for multipart/alternative
    msg['Content-Type'] = 'multipart/alternative; boundary="{}"'.format(msg.get_boundary())

    # Attach parts in order: plain text first, then HTML
    if plain_body:
        plain_part = MIMEText(plain_body, 'plain', 'utf-8')
        plain_part['Content-Type'] = 'text/plain; charset=utf-8'
        msg.attach(plain_part)
    
    if html_body:
        html_part = MIMEText(html_body, 'html', 'utf-8')
        html_part['Content-Type'] = 'text/html; charset=utf-8'
        msg.attach(html_part)
    
    # Ensure we have at least one part
    if not msg.get_payload():
        plain_part = MIMEText('', 'plain', 'utf-8')
        plain_part['Content-Type'] = 'text/plain; charset=utf-8'
        msg.attach(plain_part)

    return msg.as_bytes(policy=policy.SMTP)


def _prepare_body_payload(
    em: Dict[str, Any],
    *,
    requested_type: int = 2,
    truncation_size: Optional[int] = None,
) -> Dict[str, str]:
    html = str(em.get('body_html') or em.get('html') or '')
    plain = str(em.get('body') or em.get('preview') or '')

    body_type = requested_type if requested_type in (1, 2, 4) else 2

    if body_type == 4:
        mime_bytes = em.get('mime_content')
        if mime_bytes:
            if isinstance(mime_bytes, str):
                # MIME content in DB is base64 encoded - decode it first
                try:
                    mime_bytes = base64.b64decode(mime_bytes)
                except Exception:
                    # If decode fails, treat as raw bytes
                    mime_bytes = mime_bytes.encode('utf-8', errors='ignore')
        else:
            mime_bytes = _build_mime_message(em, html, plain)
        estimated_size = str(len(mime_bytes))
        payload_bytes, truncated_flag = _truncate_bytes(mime_bytes, truncation_size)
        data_text = base64.b64encode(payload_bytes).decode('ascii') if payload_bytes else ''
        native = '4' if payload_bytes else native_body_type
        return {
            'type': '4',
            'data': data_text,
            'estimated_size': estimated_size,
            'truncated': truncated_flag,
            'native_type': '4',
            'content_type': 'message/rfc822',
        }

    preference = 1 if body_type == 1 else 2
    content, selected_native = _select_body_content(em, body_type_preference=preference)
    body_bytes = content.encode('utf-8') if content else b''
    estimated_size = str(len(body_bytes))
    payload_bytes, truncated_flag = _truncate_bytes(body_bytes, truncation_size)
    data_text = payload_bytes.decode('utf-8', errors='ignore') if payload_bytes else ''

    actual_type = '2' if (content and selected_native == 2 and data_text) else '1'

    content_type = (
        'text/html; charset=utf-8' if actual_type == '2' else 'text/plain; charset=utf-8'
    )
    native_type = '2' if selected_native == 2 else '1'

    return {
        'type': actual_type,
        'data': data_text,
        'estimated_size': estimated_size,
        'truncated': truncated_flag,
        'native_type': native_type,
        'content_type': content_type,
    }

def write_fetch_responses(
    *,
    w: WBXMLWriter,
    fetched: List[Dict[str, Any]],
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> None:
    """Emit canonical <Responses><Fetch> blocks (Z-Push order) with proper body and no CollectionId."""
    if not fetched:
        return
    w.cp(CP_AIRSYNC)
    w.start(AS_Responses)
    for em in fetched:
        server_id = str(em.get("server_id") or em.get("id") or "")
        if not server_id:
            continue
        # <Fetch>
        w.start(AS_Fetch)
        # ORDER: ServerId -> Status -> Class -> ApplicationData
        w.start(AS_ServerId); w.write_str(server_id); w.end()
        w.start(AS_Status);   w.write_str("1");     w.end()
        w.start(AS_Class);    w.write_str("Email"); w.end()
        # <ApplicationData>
        w.start(AS_ApplicationData)
        # Optional envelope
        w.cp(CP_EMAIL)
        subj = str(em.get("subject") or "")
        frm  = str(em.get("from") or em.get("sender") or "")
        to   = str(em.get("to") or em.get("recipient") or "")
        when = _ensure_utc_z(em.get("created_at"))
        if subj:
            w.start(EM_Subject);      w.write_str(subj); w.end()
        if frm:
            w.start(EM_From);         w.write_str(frm);  w.end()
        if to:
            w.start(EM_To);           w.write_str(to);   w.end()
        if when:
            w.start(EM_DateReceived); w.write_str(when); w.end()
        w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()
        w.start(EM_InternetCPID); w.write_str("65001");    w.end()
        # Body (respect preference & truncation)
        body_payload = _prepare_body_payload(
            em,
            requested_type=body_type_preference,
            truncation_size=truncation_size,
        )
        w.cp(CP_AIRSYNCBASE)
        w.start(ASB_Body)
        w.start(ASB_Type);              w.write_str(body_payload['type']);         w.end()
        w.start(ASB_EstimatedDataSize); w.write_str(body_payload['estimated_size']); w.end()
        w.start(ASB_Truncated);         w.write_str(body_payload['truncated']);    w.end()
        w.start(ASB_Data);              w.write_str(body_payload['data']);         w.end()
        content_type = body_payload.get('content_type')
        if content_type:
            w.start(ASB_ContentType); w.write_str(content_type); w.end()
        w.end()  # </Body>
        w.start(ASB_NativeBodyType); w.write_str(body_payload['native_type']); w.end()
        # Close ApplicationData and Fetch
        w.cp(CP_AIRSYNC)
        w.end()  # </ApplicationData>
        w.end()  # </Fetch>
    w.end()  # </Responses>


def write_delete_responses(
    *,
    w: WBXMLWriter,
    deletes: List[Dict[str, Any]],
) -> None:
    """Emit <Responses><Delete> acknowledgements."""
    if not deletes:
        return
    w.cp(CP_AIRSYNC)
    w.start(AS_Responses)
    for item in deletes:
        sid = str(item.get("server_id") or "")
        status = str(item.get("status") or "1")
        # <Delete>
        w.start(AS_Delete)
        w.start(AS_Status); w.write_str(status); w.end()
        w.start(AS_ServerId); w.write_str(sid); w.end()
        w.end()  # </Delete>
    w.end()  # </Responses>


def build_sync_response(
    *,
    new_sync_key: str,
    class_name: str,
    collection_id: str,
    items: List[Dict[str, Any]],
    window_size: int,
    more_available: bool,
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    <Sync>
      <Status>1</Status>
      <Collections>
        <Collection>
          <SyncKey>...</SyncKey>
          <CollectionId>...</CollectionId>
          <Status>1</Status>
          <Class>Email</Class>
          [<MoreAvailable/>]
          <Commands>
            <Add>
              <ServerId>...</ServerId>
              <ApplicationData>
                Email:*
                AirSyncBase:Body
              </ApplicationData>
            </Add>
            ...
          </Commands>
        </Collection>
      </Collections>
    </Sync>
    """
    w = WBXMLWriter()
    w.header()

    # <Sync>
    w.page(CP_AIRSYNC)
    w.start(AS_Sync)

    # <Collections><Collection>
    w.start(AS_Collections)
    w.start(AS_Collection)

    # Required children (Z-Push-like order): SyncKey -> CollectionId -> Class -> Status
    w.start(AS_SyncKey);      w.write_str(new_sync_key);         w.end()
    w.start(AS_CollectionId); w.write_str(str(collection_id));   w.end()
    w.start(AS_Class);        w.write_str(class_name);           w.end()
    w.start(AS_Status);       w.write_str("1");                  w.end()

    count = 0
    if items:
        # Commands
        w.start(AS_Commands)

        for idx, em in enumerate(items):
            if count >= window_size:
                break

            server_id = em.get("server_id") or f"{collection_id}:{em.get('id', idx+1)}"
            subj = em.get("subject") or "(no subject)"
            from_ = em.get("from") or em.get("sender") or ""
            to_   = em.get("to") or em.get("recipient") or ""
            read  = "1" if bool(em.get("is_read")) else "0"
            when  = _ensure_utc_z(em.get("created_at"))

            body_payload = _prepare_body_payload(
                em,
                requested_type=body_type_preference,
                truncation_size=truncation_size,
            )

            # <Add>
            w.page(CP_AIRSYNC); w.start(AS_Add)

            # <ServerId>
            w.start(AS_ServerId); w.write_str(server_id); w.end()

            # <ApplicationData>
            w.start(AS_ApplicationData)

            # Email props
            w.page(CP_EMAIL)
            w.start(EM_Subject);      w.write_str(str(subj));  w.end()
            w.start(EM_From);         w.write_str(str(from_)); w.end()
            w.start(EM_To);           w.write_str(str(to_));   w.end()
            w.start(EM_DateReceived); w.write_str(when);       w.end()
            # Include MessageClass like Z-Push
            w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()
            # InternetCPID to signal UTF-8
            w.start(EM_InternetCPID); w.write_str("65001");    w.end()
            w.start(EM_Read);         w.write_str(read);       w.end()

            # AirSyncBase <Body> (always include) with preference/truncation
            w.page(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            # ORDER MATTERS: Type -> EstimatedDataSize -> Truncated -> Data
            w.start(ASB_Type);              w.write_str(body_payload['type']);          w.end()
            w.start(ASB_EstimatedDataSize); w.write_str(body_payload['estimated_size']); w.end()
            w.start(ASB_Truncated);         w.write_str(body_payload['truncated']);      w.end()
            w.start(ASB_Data);              w.write_str(body_payload['data']);           w.end()
            content_type = body_payload.get('content_type')
            if content_type:
                w.start(ASB_ContentType); w.write_str(content_type); w.end()
            w.end()  # </Body>
            # Native body type hint (as Z-Push does)
            w.page(CP_AIRSYNCBASE)
            w.start(ASB_NativeBodyType); w.write_str(body_payload['native_type']); w.end()

            # close ApplicationData, Add
            w.page(CP_AIRSYNC); w.end()     # </ApplicationData>
            w.end()                         # </Add>

            count += 1

        w.end()  # </Commands>

    # MoreAvailable after Commands
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)
    w.end()  # </Collection>
    w.end()  # </Collections>
    w.end()  # </Sync>

    return SyncBatch(
        response_sync_key=new_sync_key,
        payload=w.bytes(),
        sent_count=count,
        total_available=len(items),
        more_available=more_available,
    )


def build_foldersync_with_folders(
    sync_key: str,
    folders: List[Dict[str, str]],
) -> bytes:
    """
    Build a FolderSync response with folder hierarchy for initial sync (SyncKey 0→1).

    Parameters
    ----------
    sync_key: str
        Server sync key to advertise in the response.
    folders: list[dict]
        Each dict should contain ``server_id`` / ``id``, ``display_name`` / ``name``,
        optional ``parent_id`` (defaults to "0"), and ``type`` (Folder class code, e.g. 2=Inbox).

    CRITICAL: Pass BASE tokens WITHOUT 0x40 bit - WBXMLWriter.start() adds it automatically!
    
    Base token values for FolderHierarchy codepage (0x07):
    - FolderSync = 0x16
    - Status = 0x0B  
    - SyncKey = 0x12
    - Changes = 0x0E
    - Count = 0x07
    - Add = 0x0C
    - ServerId = 0x15
    - ParentId = 0x17
    - DisplayName = 0x08
    - Type = 0x0F
    """
    w = WBXMLWriter()
    w.header()
    
    # FolderHierarchy codepage (CP 7)
    CP_FOLDER = 0x07
    TAG_FOLDERSYNC = 0x16
    TAG_STATUS = 0x0C
    TAG_SYNCKEY = 0x12
    TAG_CHANGES = 0x0E
    TAG_COUNT = 0x17
    TAG_ADD = 0x0F
    TAG_DISPLAYNAME = 0x07
    TAG_SERVERID = 0x08
    TAG_PARENTID = 0x09
    TAG_TYPE = 0x0A

    w.page(CP_FOLDER)

    # <FolderSync>
    w.start(TAG_FOLDERSYNC)

    # <Status>1</Status>
    w.start(TAG_STATUS)
    w.write_str("1")
    w.end()

    # <SyncKey>1</SyncKey>
    w.start(TAG_SYNCKEY)
    w.write_str(sync_key)
    w.end()

    # <Changes>
    w.start(TAG_CHANGES)

    # <Count>N</Count>
    w.start(TAG_COUNT)
    w.write_str(str(len(folders)))
    w.end()

    for folder in folders:
        server_id = folder.get("server_id") or folder.get("id") or ""
        display_name = folder.get("display_name") or folder.get("name") or ""
        folder_type = folder.get("type") or "2"
        parent_id = folder.get("parent_id") or "0"

        # <Add>
        w.start(TAG_ADD)

        # <ServerId>
        w.start(TAG_SERVERID); w.write_str(str(server_id)); w.end()

        # <ParentId>
        w.start(TAG_PARENTID); w.write_str(str(parent_id)); w.end()

        # <DisplayName>
        w.start(TAG_DISPLAYNAME); w.write_str(display_name); w.end()

        # <Type>
        w.start(TAG_TYPE); w.write_str(str(folder_type)); w.end()

        w.end()  # </Add>
    w.end()  # </Changes>
    w.end()  # </FolderSync>
    
    return w.bytes()


def build_foldersync_no_changes(sync_key: str = "1") -> bytes:
    """
    Minimal FolderSync 'no changes' WBXML (keeps the device happy).
    """
    w = WBXMLWriter()
    w.header()

    CP_FOLDER = 0x07
    TAG_FOLDERSYNC = 0x16
    TAG_STATUS = 0x0C
    TAG_SYNCKEY = 0x12
    TAG_CHANGES = 0x0E
    TAG_COUNT = 0x17

    w.page(CP_FOLDER)
    w.start(TAG_FOLDERSYNC)
    w.start(TAG_STATUS); w.write_str("1"); w.end()
    w.start(TAG_SYNCKEY); w.write_str(sync_key); w.end()
    w.start(TAG_CHANGES)
    w.start(TAG_COUNT); w.write_str("0"); w.end()
    w.end()  # </Changes>
    w.end()  # </FolderSync>
    return w.bytes()


def build_provision_response(*, policy_key: str, include_policy_data: bool) -> bytes:
    """Build WBXML Provision response.

    When ``include_policy_data`` is True (phase 1), an ``EASProvisionDoc`` is emitted with
    a permissive policy document. For the final acknowledgement (phase 2) only
    the PolicyKey is returned.
    """
    w = WBXMLWriter()
    w.header()

    w.page(CP_PROVISION)
    w.start(PR_Provision)

    w.start(PR_Status); w.write_str("1"); w.end()

    w.start(PR_Policies)
    w.start(PR_Policy)

    w.start(PR_PolicyType); w.write_str("MS-EAS-Provisioning-WBXML"); w.end()
    w.start(PR_Status); w.write_str("1"); w.end()
    w.start(PR_PolicyKey); w.write_str(policy_key); w.end()

    if include_policy_data:
        w.start(PR_Data)
        w.start(PR_EASProvisionDoc)

        # Minimal permissive policy compatible with iOS expectations
        policy_fields: List[tuple[int, str]] = [
            (PR_DevicePasswordEnabled, "0"),
            (PR_AlphanumericDevicePasswordRequired, "0"),
            (PR_PasswordRecoveryEnabled, "0"),
            (PR_AttachmentsEnabled, "1"),
            (PR_MinDevicePasswordLength, "0"),
            (PR_MaxInactivityTimeDeviceLock, "0"),
            (PR_MaxDevicePasswordFailedAttempts, "0"),
            (PR_MaxAttachmentSize, "52428800"),  # 50 MB
            (PR_AllowSimpleDevicePassword, "1"),
            (PR_DevicePasswordExpiration, "0"),
            (PR_DevicePasswordHistory, "0"),
            (PR_AllowStorageCard, "1"),
            (PR_AllowCamera, "1"),
            (PR_RequireDeviceEncryption, "0"),
            (PR_AllowUnsignedApplications, "1"),
            (PR_AllowUnsignedInstallationPackages, "1"),
            (PR_MinDevicePasswordComplexCharacters, "0"),
            (PR_AllowWiFi, "1"),
            (PR_AllowTextMessaging, "1"),
            (PR_AllowPOPIMAPEmail, "1"),
            (PR_AllowBluetooth, "2"),
            (PR_AllowIrDA, "1"),
            (PR_RequireManualSyncWhenRoaming, "0"),
            (PR_AllowDesktopSync, "1"),
            (PR_MaxCalendarAgeFilter, "0"),
            (PR_AllowHTMLEmail, "1"),
            (PR_MaxEmailAgeFilter, "0"),
            (PR_MaxEmailBodyTruncationSize, "-1"),
            (PR_MaxEmailHTMLBodyTruncationSize, "-1"),
            (PR_RequireSignedSMIMEMessages, "0"),
            (PR_RequireEncryptedSMIMEMessages, "0"),
            (PR_RequireSignedSMIMEAlgorithm, "0"),
            (PR_RequireEncryptionSMIMEAlgorithm, "0"),
            (PR_AllowSMIMEEncryptionAlgorithmNegotiation, "2"),
            (PR_AllowSMIMESoftCerts, "1"),
            (PR_AllowBrowser, "1"),
            (PR_AllowConsumerEmail, "1"),
            (PR_AllowRemoteDesktop, "1"),
            (PR_AllowInternetSharing, "1"),
        ]

        for token, value in policy_fields:
            w.start(token); w.write_str(value); w.end()

        w.end()  # </EASProvisionDoc>
        w.end()  # </Data>

    w.end()  # </Policy>
    w.end()  # </Policies>
    w.end()  # </Provision>

    return w.bytes()


def extract_synckey_and_collection(wb: bytes) -> tuple[Optional[str], Optional[str]]:
    """
    Very small reader:
    - Tracks current code page via SWITCH_PAGE.
    - When CP==AirSync and token==SyncKey/CollectionId, reads the following STR_I text.
    """
    cp = None
    i = 0
    sync_key = None
    coll_id = None

    def read_cstr(buf: bytes, pos: int) -> tuple[str, int]:
        j = pos
        while j < len(buf) and buf[j] != 0x00:
            j += 1
        s = buf[pos:j].decode("utf-8", errors="ignore")
        return s, j + 1

    while i < len(wb):
        b = wb[i]; i += 1

        if b == SWITCH_PAGE:
            if i >= len(wb): break
            cp = wb[i]; i += 1
            continue

        if b == STR_I:
            # skip inline string (we only read strings after known start tags)
            while i < len(wb) and wb[i] != 0x00:
                i += 1
            i += 1
            continue

        if b == END:
            continue

        # Tag start: content bit may be set (0x40)
        tok = b & 0x3F

        if cp == CP_AIRSYNC and tok in (AS_SyncKey, AS_CollectionId):
            # Next token must be STR_I
            # We skip any attributes/content flags—only STR_I matters to us.
            # Find the next STR_I:
            while i < len(wb) and wb[i] != STR_I:
                # allow nested tags; skip until we hit the inline string
                i += 1
            if i < len(wb) and wb[i] == STR_I:
                i += 1
                text, i = read_cstr(wb, i)
                if tok == AS_SyncKey:
                    sync_key = text
                else:
                    coll_id = text
            # eat until END of current element (best-effort)
            while i < len(wb) and wb[i] != END:
                i += 1
            if i < len(wb) and wb[i] == END:
                i += 1

        if sync_key and coll_id:
            break

    return sync_key, coll_id


# Legacy compatibility functions
def create_sync_response_wbxml(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    Legacy compatibility wrapper with Z-Push body preference support.
    
    Args:
        body_type_preference: 1=PlainText, 2=HTML (default), 3=RTF, 4=MIME
        truncation_size: Max body size in bytes (None = no truncation)
    """
    return build_sync_response(
        new_sync_key=sync_key,
        class_name=class_name,
        collection_id=collection_id,
        items=emails,
        window_size=window_size,
        more_available=more_available,
        body_type_preference=body_type_preference,
        truncation_size=truncation_size,
    )


def create_sync_response_wbxml_with_fetch(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    fetched: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    Build a Sync response containing <Collections>/<Collection> with optional <Commands>/<Add>
    and also <Responses>/<Fetch> bodies for items explicitly fetched by the client.
    """
    w = WBXMLWriter()
    w.header()

    # <Sync>
    w.cp(CP_AIRSYNC)
    w.start(AS_Sync)

    # <Collections><Collection>
    w.start(AS_Collections)
    w.start(AS_Collection)

    # Required children (Z-Push-like order): SyncKey -> CollectionId -> Class -> Status
    w.start(AS_SyncKey);      w.write_str(sync_key);         w.end()
    w.start(AS_CollectionId); w.write_str(collection_id);   w.end()
    w.start(AS_Class);        w.write_str(class_name);           w.end()
    w.start(AS_Status);       w.write_str("1");                  w.end()

    # Commands for new items
    count = 0
    if emails:
        w.start(AS_Commands)
        for idx, em in enumerate(emails):
            if count >= window_size:
                break
            server_id = em.get("server_id") or f"{collection_id}:{em.get('id', idx+1)}"
            subj = str(em.get("subject") or "(no subject)")
            frm  = str(em.get("from") or em.get("sender") or "")
            to   = str(em.get("to") or em.get("recipient") or "")
            read = "1" if bool(em.get("is_read")) else "0"
            when = _ensure_utc_z(em.get("created_at"))
            # <Add>
            w.cp(CP_AIRSYNC); w.start(AS_Add)
            w.start(AS_ServerId); w.write_str(str(server_id)); w.end()
            w.start(AS_ApplicationData)
            # Email props
            w.cp(CP_EMAIL)
            w.start(EM_Subject);      w.write_str(subj);  w.end()
            w.start(EM_From);         w.write_str(frm);   w.end()
            w.start(EM_To);           w.write_str(to);    w.end()
            w.start(EM_DateReceived); w.write_str(when);  w.end()
            w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()
            w.start(EM_InternetCPID); w.write_str("65001"); w.end()
            w.start(EM_Read);         w.write_str(read);  w.end()
            # AirSyncBase Body — honor client BodyPreference and truncation
            w.cp(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            body_payload = _prepare_body_payload(
                em,
                requested_type=body_type_preference,
                truncation_size=truncation_size,
            )
            w.start(ASB_Type); w.write_str(body_payload['type']); w.end()
            w.start(ASB_EstimatedDataSize); w.write_str(body_payload['estimated_size']); w.end()
            w.start(ASB_Truncated); w.write_str(body_payload['truncated']); w.end()
            w.start(ASB_Data); w.write_str(body_payload['data']); w.end()
            content_type = body_payload.get('content_type')
            if content_type:
                w.start(ASB_ContentType); w.write_str(content_type); w.end()
            w.end()  # </Body>
            w.cp(CP_AIRSYNCBASE)
            w.start(ASB_NativeBodyType); w.write_str(body_payload['native_type']); w.end()
            # Close appdata/add
            w.cp(CP_AIRSYNC)
            w.end(); w.end()
            count += 1
        w.end()  # </Commands>

    # MoreAvailable after Commands
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)
    w.end(); w.end()  # </Collection></Collections>

    # <Responses><Fetch> for fetched items
    write_fetch_responses(
        w=w,
        fetched=fetched,
        body_type_preference=body_type_preference,
        truncation_size=truncation_size,
    )

    # Close Sync
    w.end()

    payload = w.bytes()
    return SyncBatch(
        response_sync_key=sync_key,
        payload=payload,
        sent_count=count,
        total_available=len(emails),
        more_available=more_available,
    )

def create_invalid_synckey_response_wbxml(*, collection_id: str = "1", class_name: str = "Email") -> SyncBatch:
    """
    Build a minimal response that signals Status=3 (InvalidSyncKey) and forces the client to re-init
    the collection with SyncKey=0 (per MS-ASCMD).
    """
    w = WBXMLWriter()
    w.header()

    w.page(CP_AIRSYNC)
    w.start(AS_Sync)
    w.start(AS_Status); w.write_str("3"); w.end()  # InvalidSyncKey
    w.start(AS_Collections)
    w.start(AS_Collection)
    w.start(AS_Class);        w.write_str(class_name);   w.end()
    w.start(AS_SyncKey);      w.write_str("0");          w.end()
    w.start(AS_CollectionId); w.write_str(collection_id); w.end()
    w.start(AS_Status);       w.write_str("3");          w.end()  # InvalidSyncKey
    w.end(); w.end(); w.end()

    payload = w.bytes()
    return SyncBatch(
        response_sync_key="0",
        payload=payload,
        sent_count=0,
        total_available=0,
        more_available=False,
    )
# Provision (CP 14)
PR_Provision                = 0x05
PR_Policies                 = 0x06
PR_Policy                   = 0x07
PR_PolicyType               = 0x08
PR_PolicyKey                = 0x09
PR_Data                     = 0x0A
PR_Status                   = 0x0B
PR_RemoteWipe               = 0x0C
PR_EASProvisionDoc          = 0x0D
PR_DevicePasswordEnabled    = 0x0E
PR_AlphanumericDevicePasswordRequired = 0x0F
PR_PasswordRecoveryEnabled  = 0x11
PR_AttachmentsEnabled       = 0x13
PR_MinDevicePasswordLength  = 0x14
PR_MaxInactivityTimeDeviceLock = 0x15
PR_MaxDevicePasswordFailedAttempts = 0x16
PR_MaxAttachmentSize        = 0x17
PR_AllowSimpleDevicePassword = 0x18
PR_DevicePasswordExpiration = 0x19
PR_DevicePasswordHistory    = 0x1A
PR_AllowStorageCard         = 0x1B
PR_AllowCamera              = 0x1C
PR_RequireDeviceEncryption  = 0x1D
PR_AllowUnsignedApplications = 0x1E
PR_AllowUnsignedInstallationPackages = 0x1F
PR_MinDevicePasswordComplexCharacters = 0x20
PR_AllowWiFi                = 0x21
PR_AllowTextMessaging       = 0x22
PR_AllowPOPIMAPEmail        = 0x23
PR_AllowBluetooth           = 0x24
PR_AllowIrDA               = 0x25
PR_RequireManualSyncWhenRoaming = 0x26
PR_AllowDesktopSync         = 0x27
PR_MaxCalendarAgeFilter     = 0x28
PR_AllowHTMLEmail           = 0x29
PR_MaxEmailAgeFilter        = 0x2A
PR_MaxEmailBodyTruncationSize = 0x2B
PR_MaxEmailHTMLBodyTruncationSize = 0x2C
PR_RequireSignedSMIMEMessages = 0x2D
PR_RequireEncryptedSMIMEMessages = 0x2E
PR_RequireSignedSMIMEAlgorithm = 0x2F
PR_RequireEncryptionSMIMEAlgorithm = 0x30
PR_AllowSMIMEEncryptionAlgorithmNegotiation = 0x31
PR_AllowSMIMESoftCerts      = 0x32
PR_AllowBrowser             = 0x33
PR_AllowConsumerEmail       = 0x34
PR_AllowRemoteDesktop       = 0x35
PR_AllowInternetSharing     = 0x36
PR_AccountOnlyRemoteWipe    = 0x3B
