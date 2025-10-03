#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spec-correct WBXML Sync response builder for Exchange ActiveSync 14.1 (iOS-friendly).

Key points:
- AirSync code page (0) for Sync/Collections/Collection/Commands, etc.  [MS-ASWBXML 2.1.2.1.1]
- Email code page (2) for Subject/From/To/DateReceived/Read, etc.       [MS-ASWBXML 2.1.2.1.3]
- AirSyncBase code page (17) for Body/Type/Data/EstimatedDataSize/...    [MS-ASWBXML 2.1.2.1.18]

Ordering inside AirSyncBase: put <Type> FIRST, then <EstimatedDataSize>, <Truncated>, and <Data>.
This order is accepted widely and matches many server implementations (e.g., Z-Push style).

This module exports:
- create_sync_response_wbxml(sync_key, emails, *, collection_id='1', window_size=25, more_available=False)
    -> bytes WBXML payload

It also exposes a quick to_hex() helper for logging.

This file intentionally has NO external dependencies; only Python stdlib is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

log = logging.getLogger(__name__)

# --- WBXML control tokens (WAP-192-WBXML) ---
SWITCH_PAGE = 0x00
END         = 0x01
STR_I       = 0x03

# --- Code pages (per MS-ASWBXML) ---
CP_AIRSYNC     = 0      # Code Page 0
CP_EMAIL       = 2      # Code Page 2
CP_AIRSYNCBASE = 17     # Code Page 17

# --- AirSync (CP0) tokens we use (see MS-ASWBXML 2.1.2.1.1) ---
AS_Sync           = 0x05
AS_Responses      = 0x06
AS_Add            = 0x07
AS_Change         = 0x08
AS_Delete         = 0x09
AS_Fetch          = 0x0A
AS_SyncKey        = 0x0B
AS_ClientId       = 0x0C
AS_ServerId       = 0x0D
AS_Status         = 0x0E
AS_Collection     = 0x0F
AS_Class          = 0x10
# 0x11 is reserved in this page; collection id is 0x12:
AS_CollectionId   = 0x12
AS_GetChanges     = 0x13
AS_MoreAvailable  = 0x14
AS_WindowSize     = 0x15
AS_Commands       = 0x16
AS_Collections    = 0x1C
AS_ApplicationData= 0x1D

# --- Email (CP2) tokens we use (see MS-ASWBXML 2.1.2.1.3) ---
EM_DateReceived   = 0x0F
EM_DisplayTo      = 0x11
EM_Importance     = 0x12
EM_MessageClass   = 0x13
EM_Subject        = 0x14
EM_Read           = 0x15
EM_To             = 0x16
EM_Cc             = 0x17
EM_From           = 0x18
EM_DtStamp        = 0x1D
EM_ThreadTopic    = 0x35
EM_InternetCPID   = 0x39

# --- AirSyncBase (CP17) tokens we use (see MS-ASWBXML 2.1.2.1.18) ---
ASB_Body          = 0x0A
ASB_Data          = 0x0B
ASB_EstimatedDataSize = 0x0C
ASB_Truncated     = 0x0D
ASB_Type          = 0x06

# === Simple WBXML writer ===

class WBXMLWriter:
    """
    Ultra-minimal WBXML writer for EAS.
    - Starts with a header: version=0x03, publicid=0x01, charset=utf-8 (0x6A), string table length=0x00.
    - write_str writes STR_I followed by UTF-8 bytes and zero terminator.
    - start(tag, with_content=True) writes tag | 0x40 if with_content else tag.
    - end() writes END.
    - page switches code pages only when needed.
    """
    def __init__(self):
        self.buf = bytearray()
        self.current_page = 0xFFFF  # force initial page switch

    def header(self):
        # WBXML version 1.3 (0x03), public id unknown (0x01), charset UTF-8 (0x6A), string table length 0x00
        self.buf.extend([0x03, 0x01, 0x6A, 0x00])

    def write_byte(self, b: int):
        self.buf.append(b & 0xFF)

    def write_str(self, s: str):
        self.write_byte(STR_I)
        self.buf.extend(s.encode('utf-8'))
        self.write_byte(0x00)

    def page(self, cp: int):
        if self.current_page != cp:
            self.write_byte(SWITCH_PAGE)
            self.write_byte(cp & 0xFF)
            self.current_page = cp

    def start(self, tok: int, with_content: bool = True):
        self.write_byte((tok | 0x40) if with_content else tok)

    def end(self):
        self.write_byte(END)

    def bytes(self) -> bytes:
        return bytes(self.buf)

def _wbxml_add_email(w: WBXMLWriter, server_id: str, email: Dict[str, Any], *, body_type: int = 1):
    """
    Emit one <Add> for an Email item:
    <Add>
      <ServerId>...</ServerId>
      <ApplicationData>
        <Email:Subject>...</Email:Subject>
        <Email:From>...</Email:From>
        <Email:To>...</Email:To>
        <Email:DateReceived>...</Email:DateReceived>
        <Email:Read>...</Email:Read>
        <AirSyncBase:Body>
          <AirSyncBase:Type>1</AirSyncBase:Type>
          <AirSyncBase:EstimatedDataSize>...</AirSyncBase:EstimatedDataSize>
          <AirSyncBase:Truncated>0</AirSyncBase:Truncated>
          <AirSyncBase:Data>...</AirSyncBase:Data>
        </AirSyncBase:Body>
      </ApplicationData>
    </Add>
    """
    # <Add>
    w.page(CP_AIRSYNC)
    w.start(AS_Add)

    # <ServerId> (EAS server-defined unique id per collection)
    w.start(AS_ServerId); w.write_str(server_id); w.end()

    # <ApplicationData>
    w.start(AS_ApplicationData)

    # Switch to Email CP for properties
    w.page(CP_EMAIL)

    subj = email.get('subject') or '(no subject)'
    from_ = email.get('from') or email.get('sender') or ''
    to_   = email.get('to') or email.get('recipient') or ''
    read  = '1' if bool(email.get('is_read')) else '0'
    # RFC3339 or EAS date? EAS DateReceived expects UTC in ISO 8601; iOS accepts RFC3339 with 'Z'
    created_at = email.get('created_at')
    if isinstance(created_at, datetime):
        created_utc = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        date_str = created_utc.isoformat(timespec='seconds') + 'Z'
    else:
        # assume already "YYYY-MM-DDTHH:MM:SS.sssZ" or string
        date_str = str(created_at) if created_at else datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    # Minimal required email fields
    w.start(EM_Subject);      w.write_str(subj);      w.end()
    w.start(EM_From);         w.write_str(from_);     w.end()
    w.start(EM_To);           w.write_str(to_);       w.end()
    w.start(EM_DateReceived); w.write_str(date_str);  w.end()
    w.start(EM_Read);         w.write_str(read);      w.end()

    # Body is in AirSyncBase CP
    w.page(CP_AIRSYNCBASE)
    body_bytes = (email.get('body') or '').encode('utf-8')
    body_text = (email.get('body') or '')
    est_size = str(len(body_bytes))

    w.start(ASB_Body)
    # IMPORTANT ORDER: Type -> EstimatedDataSize -> Truncated -> Data
    w.start(ASB_Type);              w.write_str(str(body_type)); w.end()      # 1 = PlainText
    w.start(ASB_EstimatedDataSize); w.write_str(est_size);       w.end()
    w.start(ASB_Truncated);         w.write_str('0');            w.end()
    w.start(ASB_Data);              w.write_str(body_text);      w.end()
    w.end()  # </Body>

    # Back to AirSync to close ApplicationData
    w.page(CP_AIRSYNC)
    w.end()  # </ApplicationData>

    # </Add>
    w.end()

@dataclass
class SyncBatch:
    """
    Represents one Sync batch worth of items produced for a given request.
    """
    response_sync_key: str
    wbxml: bytes
    sent_count: int
    total_available: int
    more_available: bool

def create_sync_response_wbxml(
    sync_key: str,
    emails: List[Dict[str, Any]],
    *,
    collection_id: str = '1',
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = 'Email'
) -> SyncBatch:
    """
    Build a minimal, standards-compliant Sync response with Add commands.

    Arguments:
        sync_key        - the *new* SyncKey that the server is issuing in this response (e.g., "12")
        emails          - the slice of emails to include in this batch
        collection_id   - EAS collection id (e.g., "1")
        window_size     - echoed for easy logging; we will not include more than this many items
        more_available  - if True, emit <MoreAvailable/> within the collection
        class_name      - typically "Email"

    Returns:
        SyncBatch with WBXML bytes and metadata for logging.
    """
    w = WBXMLWriter()
    w.header()

    # Outer structure: <Sync><Collections><Collection>...</Collection></Collections></Sync>
    w.page(CP_AIRSYNC)
    w.start(AS_Sync)                   # <Sync>
    w.start(AS_Collections)            #   <Collections>
    w.start(AS_Collection)             #     <Collection>

    # Required collection children
    w.start(AS_SyncKey);      w.write_str(sync_key);            w.end()  # <SyncKey>new</SyncKey>
    w.start(AS_CollectionId); w.write_str(str(collection_id));  w.end()
    w.start(AS_Status);       w.write_str('1');                 w.end()  # Success per MS-ASCMD
    w.start(AS_Class);        w.write_str(class_name);          w.end()

    if more_available:
        # Empty tag (no content bit, no END)
        w.start(AS_MoreAvailable, with_content=False)

    # Commands
    w.start(AS_Commands)

    # Emit up to window_size items
    max_items = min(len(emails), max(0, int(window_size or 0)))
    for idx, email in enumerate(emails[:max_items], 1):
        # ServerId format "collectionId:messageLocalId" is widely used and accepted by iOS
        server_id = f"{collection_id}:{email.get('id', idx)}"
        _wbxml_add_email(w, server_id, email)

    w.end()  # </Commands>

    # Close up
    w.end()  # </Collection>
    w.end()  # </Collections>
    w.end()  # </Sync>

    payload = w.bytes()

    # Basic debug help
    first_20 = payload[:20].hex()
    log.debug(
        "WBXML built: sync_key=%s collection=%s window=%s items=%s more=%s first20=%s size=%d",
        sync_key, collection_id, window_size, max_items, more_available, first_20, len(payload)
    )

    return SyncBatch(
        response_sync_key=sync_key,
        wbxml=payload,
        sent_count=max_items,
        total_available=len(emails),
        more_available=more_available
    )

def to_hex(b: bytes, limit: Optional[int] = None) -> str:
    """Convenience for logging."""
    hx = b.hex()
    return hx if limit is None else hx[:limit]
