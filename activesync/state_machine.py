#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
state_machine.py — Idempotent EAS Sync state machine.

Key, cursor, and pending batch are keyed by (user, device_id, collection_id).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, List, Any, Optional
import logging

from .wbxml_builder import build_sync_response, SyncBatch

log = logging.getLogger(__name__)

@dataclass
class _Ctx:
    cur_key: str = "0"         # last ACKed key from client
    next_key: str = "1"        # key we will *send* in our next response
    cursor: int = 0            # index into email list
    pending: Optional[SyncBatch] = None  # last batch we sent but not yet ACKed

class SyncStateStore:
    def __init__(self):
        self._m: Dict[Tuple[str,str,str], _Ctx] = {}

    def _k(self, user: str, device_id: str, collection_id: str) -> Tuple[str,str,str]:
        return (user, device_id, collection_id)

    @staticmethod
    def _inc(k: str) -> str:
        try:
            return str(int(k) + 1)
        except Exception:
            return "1"

    def get_ctx(self, user: str, device_id: str, collection_id: str) -> _Ctx:
        return self._m.setdefault(self._k(user, device_id, collection_id), _Ctx())

    def prepare(
        self,
        *,
        user: str,
        device_id: str,
        collection_id: str,
        client_sync_key: str,
        emails: List[Dict[str, Any]],
        window_size: int = 25
    ) -> SyncBatch:
        """
        Core rules:
        - If client_sync_key == ctx.cur_key and ctx.pending exists: **resend the same batch**.
        - If client_sync_key == ctx.next_key: client ACKed; advance keys & clear pending; make fresh batch.
        - If client_sync_key == ctx.cur_key and no pending: first batch for this round; make new; set pending.
        - Else (unexpected): keep ctx.cur_key, do NOT reset keys; serve batch for ctx.cur_key.
        """
        ctx = self.get_ctx(user, device_id, collection_id)

        if ctx.pending and client_sync_key == ctx.cur_key:
            log.info("resend_pending: user=%s dev=%s coll=%s key=%s -> response=%s",
                     user, device_id, collection_id, client_sync_key, ctx.pending.response_sync_key)
            return ctx.pending

        if client_sync_key == ctx.next_key:
            # ACK of our previous response
            ctx.cur_key = ctx.next_key
            ctx.next_key = self._inc(ctx.next_key)
            ctx.pending = None  # previous batch is now acked

        if client_sync_key == ctx.cur_key:
            start = ctx.cursor
            end = min(start + max(1, int(window_size or 1)), len(emails))
            slice_ = emails[start:end]
            more = end < len(emails)

            batch = build_sync_response(
                new_sync_key=ctx.next_key,
                class_name="Email",
                collection_id=collection_id,
                items=slice_,
                window_size=window_size,
                more_available=more,
            )
            ctx.pending = batch
            if more:
                ctx.cursor = end
            else:
                ctx.cursor = 0

            log.info("batch_generated: user=%s dev=%s coll=%s client_key=%s -> response_key=%s sent=%d total=%d more=%s",
                     user, device_id, collection_id, client_sync_key,
                     batch.response_sync_key, batch.sent_count, batch.total_available, batch.more_available)
            return batch

        log.warning("unexpected_key: user=%s dev=%s coll=%s got=%s expected_cur=%s next=%s",
                    user, device_id, collection_id, client_sync_key, ctx.cur_key, ctx.next_key)
        # Serve flow anchored to cur_key (no key rollback)
        return self.prepare(user=user, device_id=device_id, collection_id=collection_id,
                            client_sync_key=ctx.cur_key, emails=emails, window_size=window_size)

    # Legacy compatibility
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
        """Legacy compatibility wrapper."""
        return self.prepare(
            user=user_email,
            device_id=device_id,
            collection_id=collection_id,
            client_sync_key=client_sync_key,
            emails=emails,
            window_size=window_size,
        )