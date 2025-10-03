#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Sync state machine for EAS "Sync" command.

Fixes typical "looping" due to not persisting server SyncKey across requests and
not resending the same batch idempotently when the client retries with the same
client SyncKey.

Usage:
    store = SyncStateStore()
    batch = store.prepare_batch(
        user="yonatan@shtrum.com",
        device_id="KO090MSD...",
        collection_id="1",
        client_sync_key="11",
        emails=emails_list,
        window_size=1,  # keep small to exercise paging
    )
    # send batch.wbxml as HTTP body

This module keeps state in-memory. Replace the DictStorage with your DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import logging
from .wbxml_builder import create_sync_response_wbxml, SyncBatch

log = logging.getLogger(__name__)

@dataclass
class _Key:
    user: str
    device_id: str
    collection_id: str

    def k(self) -> Tuple[str, str, str]:
        return (self.user, self.device_id, self.collection_id)

@dataclass
class _Ctx:
    cur_key: str = "0"             # last ACKed key from client (what client is allowed to send)
    next_key: str = "1"            # key we will include in the *next* response we generate
    pending: Optional[SyncBatch] = None
    cursor: int = 0                # pagination cursor (index into emails for this demo)

class SyncStateStore:
    def __init__(self):
        self._state: Dict[Tuple[str, str, str], _Ctx] = {}

    def _get(self, key: _Key) -> _Ctx:
        return self._state.setdefault(key.k(), _Ctx())

    def _advance_key(self, k: str) -> str:
        try:
            return str(int(k) + 1)
        except Exception:
            return "1" if k != "1" else "2"

    def prepare_batch(
        self,
        *,
        user: str,
        device_id: str,
        collection_id: str,
        client_sync_key: str,
        emails: List[dict],
        window_size: int = 25
    ) -> SyncBatch:
        """
        Build (or re-send) a Sync batch based on the client's SyncKey.

        Rules implemented (per EAS behavior and Z-Push):
        - If client_sync_key == ctx.cur_key and ctx.pending exists: resend *same* pending batch
          with the same response SyncKey (idempotent retry).
        - If client_sync_key == ctx.next_key: client ACKed previous batch; advance keys/cursor and
          generate a fresh batch with a *new* response SyncKey.
        - If client_sync_key == ctx.cur_key and no pending: generate first batch for this round.
        - Else: treat as stale/unknown (reset cursor, set keys so that we produce a new batch).
        """
        key = _Key(user, device_id, collection_id)
        ctx = self._get(key)

        # Idempotent resend
        if ctx.pending and client_sync_key == ctx.cur_key:
            log.info("sync_resend_pending: client_key=%s server_next_key=%s", client_sync_key, ctx.next_key)
            return ctx.pending

        # ACK received (client sends the next_key we previously issued)
        if client_sync_key == ctx.next_key:
            ctx.cur_key = ctx.next_key
            ctx.next_key = self._advance_key(ctx.next_key)
            ctx.pending = None  # previous pending is acknowledged

        # If client is in expected state (either initial or after ack), produce new batch
        if client_sync_key == ctx.cur_key:
            start = ctx.cursor
            end = min(start + max(1, int(window_size or 1)), len(emails))
            slice_emails = emails[start:end]
            more = end < len(emails)

            batch = create_sync_response_wbxml(
                sync_key=ctx.next_key,
                emails=slice_emails,
                collection_id=collection_id,
                window_size=window_size,
                more_available=more,
            )

            # Persist state for idempotent resend until ACK arrives
            ctx.pending = batch
            if more:
                ctx.cursor = end  # advance cursor only after sending
            else:
                # no more, reset for next full cycle
                ctx.cursor = 0

            log.info(
                "sync_batch_generated: client_key=%s response_sync_key=%s sent=%s total=%s more=%s",
                client_sync_key, batch.response_sync_key, batch.sent_count, batch.total_available, batch.more_available
            )
            return batch

        # Unexpected key: reset cursor and serve a fresh batch from the beginning,
        # but do NOT roll back ctx.cur_key. This behavior prevents loops due to
        # server-side resets.
        log.warning(
            "sync_unexpected_key: got=%s expected_cur=%s next=%s -> resetting cursor and serving new batch",
            client_sync_key, ctx.cur_key, ctx.next_key
        )
        ctx.cursor = 0
        # Do not touch cur_key; generate a new batch keyed to current flow
        return self.prepare_batch(
            user=user,
            device_id=device_id,
            collection_id=collection_id,
            client_sync_key=ctx.cur_key,
            emails=emails,
            window_size=window_size
        )

