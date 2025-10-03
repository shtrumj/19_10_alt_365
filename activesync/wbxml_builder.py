#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bare-minimum WBXML writer for EAS Sync responses.

- Code pages and tokens taken from MS-ASWBXML:
  * CP0  AirSync:   Sync(0x05), Add(0x07), Delete(0x09), SyncKey(0x0B), ServerId(0x0D),
                    Status(0x0E), Collection(0x0F), Class(0x10), CollectionId(0x12),
                    MoreAvailable(0x14), Commands(0x16), ApplicationData(0x1D), Collections(0x1C)
  * CP2  Email:     DateReceived(0x0F), MessageClass(0x13), Subject(0x14), Read(0x15),
                    To(0x16), Cc(0x17), From(0x18)
  * CP17 AirSyncBase: Body(0x0A), Type(0x06 in this CP), Data(0x0C), EstimatedDataSize(0x0D), Truncated(0x0E)

References:
- AirSync CP0: https://learn.microsoft.com/openspecs/exchange_server_protocols/ms-aswbxml/a4b75c96-c8e3-4dc4-867a-ef7b190313cc
- Email   CP2: https://learn.microsoft.com/openspecs/exchange_server_protocols/ms-aswbxml/06f4ff28-ac7b-4c56-a9e2-6eb33dc55c83
- AirSyncBase CP17: https://learn.microsoft.com/openspecs/exchange_server_protocols/ms-aswbxml/aa548cbc-b15f-4dc1-8bda-82b35d9d41c4
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# WBXML control bytes
SWITCH_PAGE = 0x00
END         = 0x01
STR_I       = 0x03

# Header: version 1.3 (0x03), public id unknown (0x01), UTF-8 (0x6A), string table length = 0x00
WBXML_VERSION = 0x03
WBXML_PUBLIC_ID = 0x01
WBXML_CHARSET_UTF8 = 0x6A

# Code pages
CP_AIRSYNC     = 0    # MS-ASWBXML CP0
CP_EMAIL       = 2    # MS-ASWBXML CP2
CP_AIRSYNCBASE = 17   # MS-ASWBXML CP17

# --- AirSync (CP0) tokens we use ---
AS_Sync           = 0x05
AS_Add            = 0x07
AS_Delete         = 0x09
AS_SyncKey        = 0x0B
AS_ServerId       = 0x0D
AS_Status         = 0x0E
AS_Collection     = 0x0F
AS_Class          = 0x10
AS_CollectionId   = 0x12
AS_MoreAvailable  = 0x14
AS_Commands       = 0x16
AS_ApplicationData= 0x1D
AS_Collections    = 0x1C

# --- Email (CP2) tokens we use ---
EM_DateReceived   = 0x0F
EM_MessageClass   = 0x13
EM_Subject        = 0x14
EM_Read           = 0x15
EM_To             = 0x16
EM_Cc             = 0x17
EM_From           = 0x18

# --- AirSyncBase (CP17) tokens we use ---
ASB_Body          = 0x0A
ASB_Type          = 0x06
ASB_Data          = 0x0C
ASB_EstimatedDataSize = 0x0D
ASB_Truncated     = 0x0E


class WBXMLWriter:
    def __init__(self):
        self.buf: bytearray = bytearray()
        self.current_page: Optional[int] = None

    def header(self):
        self.write_byte(WBXML_VERSION)
        self.write_byte(WBXML_PUBLIC_ID)
        self.write_byte(WBXML_CHARSET_UTF8)
        self.write_byte(0x00)  # string table length

    # low-level
    def write_byte(self, b: int):
        self.buf.append(b & 0xFF)

    def write_mb_u_int(self, value: int):
        # minimum MB-U-Int (most implementations just write the single byte)
        if value < 0x80:
            self.write_byte(value)
            return
        # generic encoder
        stack = []
        while value:
            stack.append(value & 0x7F)
            value >>= 7
        while stack:
            b = stack.pop()
            if stack:
                self.write_byte(0x80 | b)
            else:
                self.write_byte(b)

    def write_str(self, s: str):
        if s is None:
            s = ""
        b = s.encode("utf-8")
        self.write_byte(STR_I)
        self.buf.extend(b)
        self.write_byte(0x00)  # null terminator

    def cp(self, codepage: int):
        if self.current_page != codepage:
            self.write_byte(SWITCH_PAGE)
            self.write_byte(codepage)
            self.current_page = codepage

    def start(self, tok: int, with_content: bool = True):
        # bit 6 set (0x40) => tag has content
        self.write_byte((tok | 0x40) if with_content else tok)

    def end(self):
        self.write_byte(END)

    def bytes(self) -> bytes:
        return bytes(self.buf)


@dataclass
class SyncBatch:
    response_sync_key: str
    wbxml: bytes
    sent_count: int
    total_available: int
    more_available: bool


def _wbxml_add_email(w: WBXMLWriter, server_id: str, email: Dict[str, Any]) -> None:
    """
    <Add>
      <ServerId>...</ServerId>
      <ApplicationData>... CP2/CP17 fields ...</ApplicationData>
    </Add>
    """
    # <Add>
    w.cp(CP_AIRSYNC)
    w.start(AS_Add)

    # <ServerId>
    w.start(AS_ServerId); w.write_str(server_id); w.end()

    # <ApplicationData>
    w.start(AS_ApplicationData)

    # Minimal, safe Email:Subject, From, To, Read, DateReceived
    subj = str(email.get("subject") or "No Subject")
    frm  = str(email.get("from") or email.get("sender") or "")
    to   = str(email.get("to") or email.get("recipient") or "")
    read = "1" if bool(email.get("is_read")) else "0"

    # DateReceived: UTC ISO8601 with trailing Z
    created_at = email.get("created_at")
    if isinstance(created_at, datetime):
        dt = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        date_str = dt.isoformat(timespec="seconds") + "Z"
    else:
        date_str = str(created_at) if created_at else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    # Email CP2 fields
    w.cp(CP_EMAIL)
    w.start(EM_Subject);      w.write_str(subj);     w.end()
    w.start(EM_From);         w.write_str(frm);      w.end()
    w.start(EM_To);           w.write_str(to);       w.end()
    w.start(EM_Read);         w.write_str(read);     w.end()
    w.start(EM_DateReceived); w.write_str(date_str); w.end()
    # MessageClass is recommended; iOS likes "IPM.Note"
    w.start(EM_MessageClass); w.write_str("IPM.Note"); w.end()

    # AirSyncBase Body (very small, safe text body)
    body_text = str(email.get("preview") or email.get("body") or email.get("snippet") or "")
    if body_text:
        w.cp(CP_AIRSYNCBASE)
        w.start(ASB_Body)
        # Type=1 (PlainText)
        w.start(ASB_Type); w.write_str("1"); w.end()
        # Data (may be truncated implicitly)
        w.start(ASB_Data); w.write_str(body_text); w.end()
        # EstimatedDataSize
        w.start(ASB_EstimatedDataSize); w.write_str(str(len(body_text.encode("utf-8")))); w.end()
        # Truncated=0 or 1 – keep 0 for now
        w.start(ASB_Truncated); w.write_str("0"); w.end()
        w.end()  # </Body>

    # </ApplicationData>
    w.cp(CP_AIRSYNC)
    w.end()

    # </Add>
    w.end()


def create_sync_response_wbxml(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
) -> SyncBatch:
    """
    Build a standards-compliant Sync response containing <Add> commands (or empty if no changes).
    Order within <Collection> mirrors common servers (Class -> SyncKey -> CollectionId -> Status -> [Commands] -> [MoreAvailable]).
    Status=1 (Success).
    """
    w = WBXMLWriter()
    w.header()

    # <Sync>
    w.cp(CP_AIRSYNC)
    w.start(AS_Sync)

    # <Collections>
    w.start(AS_Collections)

    # <Collection>
    w.start(AS_Collection)

    # Class, SyncKey, CollectionId, Status
    w.start(AS_Class);        w.write_str(class_name);     w.end()
    w.start(AS_SyncKey);      w.write_str(sync_key);        w.end()
    w.start(AS_CollectionId); w.write_str(collection_id);   w.end()
    w.start(AS_Status);       w.write_str("1");             w.end()  # Success

    # Commands (optional if no items)
    if emails:
        w.start(AS_Commands)
        for e in emails:
            server_id = str(e.get("server_id") or e.get("id") or "")
            _wbxml_add_email(w, server_id, e)
        w.end()  # </Commands>

    # MoreAvailable (if pagination)
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)

    # </Collection>, </Collections>, </Sync>
    w.end(); w.end(); w.end()

    payload = w.bytes()
    return SyncBatch(
        response_sync_key=sync_key,
        wbxml=payload,
        sent_count=len(emails),
        total_available=len(emails),  # fill with slice size; your HTTP layer can log totals separately
        more_available=more_available,
    )


def create_invalid_synckey_response_wbxml(*, collection_id: str = "1", class_name: str = "Email") -> SyncBatch:
    """
    Build a minimal response that signals Status=3 (InvalidSyncKey) and forces the client to re-init
    the collection with SyncKey=0 (per MS-ASCMD).
    """
    w = WBXMLWriter()
    w.header()

    w.cp(CP_AIRSYNC)
    w.start(AS_Sync)
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
        wbxml=payload,
        sent_count=0,
        total_available=0,
        more_available=False,
    )
