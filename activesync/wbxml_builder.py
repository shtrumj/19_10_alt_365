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
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# WBXML control
SWITCH_PAGE = 0x00
END         = 0x01
STR_I       = 0x03

# Code pages
CP_AIRSYNC     = 0
CP_PING        = 1  # Ping codepage for push notifications
CP_EMAIL       = 2
CP_AIRSYNCBASE = 17

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

def write_fetch_responses(
    *,
    w: WBXMLWriter,
    fetched: List[Dict[str, Any]],
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> None:
    """Emit <Responses><Fetch>...</Fetch></Responses> with bodies for fetched items."""
    if not fetched:
        return
    w.cp(CP_AIRSYNC)
    w.start(AS_Responses)
    for em in fetched:
        server_id = str(em.get("server_id") or em.get("id") or "")
        w.start(AS_Fetch)
        # Status 1
        w.start(AS_Status); w.write_str("1"); w.end()
        w.start(AS_ServerId); w.write_str(server_id); w.end()
        w.start(AS_Class); w.write_str("Email"); w.end()
        # ApplicationData
        w.start(AS_ApplicationData)
        # Minimal email envelope
        w.cp(CP_EMAIL)
        w.start(EM_Subject);      w.write_str(str(em.get("subject") or "(no subject)")); w.end()
        w.start(EM_From);         w.write_str(str(em.get("from") or em.get("sender") or "")); w.end()
        w.start(EM_To);           w.write_str(str(em.get("to") or em.get("recipient") or "")); w.end()
        when = _ensure_utc_z(em.get("created_at"))
        w.start(EM_DateReceived); w.write_str(when); w.end()
        w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()
        w.start(EM_InternetCPID); w.write_str("65001"); w.end()
        # AirSyncBase Body (HTML preferred)
        html = str(em.get("body_html") or em.get("html") or "")
        plain = str(em.get("body") or em.get("preview") or "")
        content = html if (body_type_preference == 2 and html) else (plain or html)
        body_bytes = content.encode("utf-8")
        out_bytes = body_bytes
        truncated_flag = "0"
        if truncation_size is not None and len(body_bytes) > int(truncation_size):
            out_bytes = body_bytes[:int(truncation_size)]
            truncated_flag = "1"
        w.cp(CP_AIRSYNCBASE)
        w.start(ASB_Body)
        w.start(ASB_Type); w.write_str("2" if content == html else "1"); w.end()
        w.start(ASB_EstimatedDataSize); w.write_str(str(len(body_bytes))); w.end()
        w.start(ASB_Truncated); w.write_str(truncated_flag); w.end()
        w.start(ASB_Data); w.write_str(out_bytes.decode("utf-8")); w.end()
        w.end()  # </Body>
        # Close
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

            # Prefer HTML body if available; otherwise plain text
            body_html = em.get("body_html")
            body_text = em.get("body") or em.get("preview") or ""
            chosen_body = str(body_html) if body_html else str(body_text)
            body_bytes = chosen_body.encode("utf-8")
            size = str(len(body_bytes))

            # <Add>
            w.page(CP_AIRSYNC); w.start(AS_Add)

            # <ServerId>
            w.start(AS_ServerId); w.write_str(server_id); w.end()

            # <ApplicationData>
            w.start(AS_ApplicationData)

            # Email props
            w.page(CP_EMAIL)
            w.start(EM_Subject);      w.write_str(subj);  w.end()
            w.start(EM_From);         w.write_str(from_); w.end()
            w.start(EM_To);           w.write_str(to_);   w.end()
            w.start(EM_DateReceived); w.write_str(when);  w.end()
            # Include MessageClass like Z-Push
            w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()
            # InternetCPID to signal UTF-8
            w.start(EM_InternetCPID); w.write_str("65001"); w.end()
            w.start(EM_Read);         w.write_str(read);  w.end()

            # AirSyncBase <Body> (always include)
            w.page(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            # ORDER MATTERS: Type -> EstimatedDataSize -> Truncated -> Data
            w.start(ASB_Type);              w.write_str("2" if body_html else "1");    w.end()  # 2=HTML,1=PlainText
            w.start(ASB_EstimatedDataSize); w.write_str(size if chosen_body else "0");   w.end()
            w.start(ASB_Truncated);         w.write_str("0");    w.end()
            w.start(ASB_Data);              w.write_str(chosen_body if chosen_body else ""); w.end()
            w.end()  # </Body>
            # Native body type helps clients choose renderer
            # (some clients expect this under AirSyncBase)
            # Not all schema versions define NativeBodyType; if unsupported, clients ignore it.

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


def build_foldersync_no_changes(sync_key: str = "1") -> bytes:
    """
    Minimal FolderSync 'no changes' WBXML (keeps the device happy).
    """
    w = WBXMLWriter()
    w.header()
    # FolderHierarchy is CP 7 in MS-ASWBXML, but most clients accept the tiny
    # no-changes response in AirSync page with just <Status> and same <SyncKey>.
    # For strictness you'd implement real FolderHierarchy CP; this minimal one
    # mirrors what many home servers do for steady-state.
    w.page(CP_AIRSYNC)
    w.start(AS_Sync)
    w.start(AS_Status);  w.write_str("1"); w.end()
    w.start(AS_SyncKey); w.write_str(sync_key); w.end()
    w.end()
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
            # Body selection
            body_html = em.get("body_html")
            body_text = str(em.get("body") or em.get("preview") or "")
            chosen_body = str(body_html) if body_html else body_text
            body_bytes = chosen_body.encode("utf-8")

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
            # AirSyncBase Body (HTML preferred)
            w.cp(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            w.start(ASB_Type); w.write_str("2" if body_html else "1"); w.end()
            w.start(ASB_EstimatedDataSize); w.write_str(str(len(body_bytes))); w.end()
            w.start(ASB_Truncated); w.write_str("0"); w.end()
            w.start(ASB_Data); w.write_str(chosen_body if chosen_body else ""); w.end()
            w.end()  # </Body>
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