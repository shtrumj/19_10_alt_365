#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sync state machine with strict InvalidSyncKey handling.

Key behaviors vs. before:
- If client_sync_key == "0": initialize collection (no changes, server returns new SyncKey "1").
- If client_sync_key == ctx.cur_key: resend the last pending batch if any; otherwise compute a fresh batch.
- If client_sync_key == ctx.next_key: treat as ACK, commit next_key -> cur_key and clear pending.
- Otherwise (stale/unknown key): return Status=3 (InvalidSyncKey) with <SyncKey>0</SyncKey> and
  reset server-side state for this collection. (MS-ASCMD §2.2.2.20 Status=3). 
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

from .wbxml_builder import (
    create_sync_response_wbxml,
    create_invalid_synckey_response_wbxml,
    SyncBatch,
)

# A "collection" is uniquely identified by (user_email, device_id, collection_id).
CollectionKey = Tuple[str, str, str]


@dataclass
class CollectionState:
    cur_key: str = "0"              # last ACKed key
    next_key: Optional[str] = None  # key we issued in the last batch (awaiting ACK)
    pending_wbxml: Optional[bytes] = None
    cursor: int = 0                 # simple pagination cursor (highest index sent)
    last_slice_count: int = 0       # for logging / resend sanity


class SyncStateStore:
    def __init__(self):
        self._state: Dict[CollectionKey, CollectionState] = {}

    # ---------- public API ----------

    def prepare_batch(
        self,
        *,
        user_email: str,
        device_id: str,
        collection_id: str,
        client_sync_key: str,
        emails: List[Dict[str, Any]],
        window_size: int = 25,
    ) -> SyncBatch:
        """
        Compute the correct response to a Sync request for one collection.
        Returns a SyncBatch whose WBXML can be written to the HTTP response.
        """

        key: CollectionKey = (user_email, device_id, collection_id)
        ctx = self._state.setdefault(key, CollectionState())

        # 1) INITIALIZATION HANDSHAKE
        if client_sync_key == "0":
            # Reset server view for this collection and assign fresh first key "1"
            self._reset_state(key)
            ctx = self._state[key]
            new_key = "1"
            ctx.cur_key = "0"
            ctx.next_key = new_key
            # Initial sync per spec: return only <SyncKey>1</SyncKey> and Status=1 (no commands)
            batch = create_sync_response_wbxml(
                sync_key=new_key,
                emails=[],                         # no changes on initial
                collection_id=collection_id,
                window_size=window_size,
                more_available=False,
                class_name="Email",
            )
            # Keep as pending until client ACKs with "1"
            ctx.pending_wbxml = batch.wbxml
            ctx.last_slice_count = 0
            return batch

        # 2) EXACT MATCH TO CURRENT KEY --> (re)SEND PENDING OR COMPUTE NEW BATCH
        if client_sync_key == ctx.cur_key:
            # If there is a pending batch (we already issued next_key) just resend it idempotently.
            if ctx.pending_wbxml and ctx.next_key is not None:
                # Resend the *exact same* bytes and *same* SyncKey as before
                return SyncBatch(
                    response_sync_key=ctx.next_key,
                    wbxml=ctx.pending_wbxml,
                    sent_count=ctx.last_slice_count,
                    total_available=max(ctx.cursor, len(emails)),
                    more_available=False,  # value doesn't matter; payload is identical
                )

            # No pending batch -> compute a fresh one from cursor forward
            start = ctx.cursor
            end = min(len(emails), start + max(1, int(window_size)))
            slice_ = emails[start:end]
            more = end < len(emails)

            new_key_int = int(ctx.cur_key) + 1
            new_key = str(new_key_int)

            batch = create_sync_response_wbxml(
                sync_key=new_key,
                emails=slice_,
                collection_id=collection_id,
                window_size=window_size,
                more_available=more,
                class_name="Email",
            )

            # Stage as pending until ACK
            ctx.next_key = new_key
            ctx.pending_wbxml = batch.wbxml
            ctx.last_slice_count = len(slice_)
            # Do NOT advance cursor yet; we only commit when client ACKs (sends client_sync_key == next_key)
            return batch

        # 3) CLIENT IS ACKING THE PREVIOUS BATCH (client_sync_key == ctx.next_key)
        if ctx.next_key is not None and client_sync_key == ctx.next_key:
            # Commit: next_key becomes current, pending cleared, and cursor advances by last slice count.
            ctx.cur_key = ctx.next_key
            ctx.next_key = None
            ctx.pending_wbxml = None
            ctx.cursor = min(len(emails), ctx.cursor + ctx.last_slice_count)
            ctx.last_slice_count = 0

            # Now prepare the next fresh batch (which may be empty)
            start = ctx.cursor
            end = min(len(emails), start + max(1, int(window_size)))
            slice_ = emails[start:end]
            more = end < len(emails)

            if not slice_ and not more:
                # No changes -> return empty response with *same* SyncKey (cur_key)
                return create_sync_response_wbxml(
                    sync_key=ctx.cur_key,
                    emails=[],
                    collection_id=collection_id,
                    window_size=window_size,
                    more_available=False,
                    class_name="Email",
                )

            new_key_int = int(ctx.cur_key) + 1
            new_key = str(new_key_int)

            batch = create_sync_response_wbxml(
                sync_key=new_key,
                emails=slice_,
                collection_id=collection_id,
                window_size=window_size,
                more_available=more,
                class_name="Email",
            )

            ctx.next_key = new_key
            ctx.pending_wbxml = batch.wbxml
            ctx.last_slice_count = len(slice_)
            return batch

        # 4) ANY OTHER KEY -> MUST TELL CLIENT IT'S INVALID AND FORCE RE-INIT
        # (This is what stops the 61/5 ping-pong you're seeing.)
        # Spec requires the collection to go back to SyncKey 0. (MS-ASCMD, Status=3)
        self._reset_state(key)
        invalid = create_invalid_synckey_response_wbxml(collection_id=collection_id)
        # Keep state at 0; the client will send SyncKey=0 next.
        return invalid

    # ---------- utilities ----------

    def _reset_state(self, key: CollectionKey) -> None:
        self._state[key] = CollectionState()
