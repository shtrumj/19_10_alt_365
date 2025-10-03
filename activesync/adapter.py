#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Thin adapter between your FastAPI layer and the state machine/builder.

- Converts your DB Email rows -> builder-friendly dicts.
- Holds one in-process SyncStateStore (swap with persistent storage if desired).
"""

from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime
from .state_machine import SyncStateStore
from .wbxml_builder import SyncBatch

# One in-memory store (replace with a DB-backed implementation if needed)
STORE = SyncStateStore()


def _row_to_email_dict(row: Any) -> Dict[str, Any]:
    # Accept both dict-like and attribute-like rows
    g = (row if isinstance(row, dict) else row.__dict__)
    return {
        "id": g.get("id"),
        "server_id": g.get("server_id") or g.get("id"),
        "subject": g.get("subject") or "No Subject",
        "from": g.get("sender") or g.get("from") or g.get("external_sender"),
        "to": g.get("recipient") or g.get("to") or g.get("external_recipient"),
        "is_read": bool(g.get("is_read")),
        "created_at": g.get("created_at") if isinstance(g.get("created_at"), datetime) else g.get("created_at"),
        "body": g.get("body") or g.get("preview") or g.get("snippet") or "",
    }


def sync_prepare_batch(
    *,
    user_email: str,
    device_id: str,
    collection_id: str,
    client_sync_key: str,
    db_emails: List[Any],
    window_size: int = 25,
) -> SyncBatch:
    emails = [_row_to_email_dict(r) for r in db_emails]

    return STORE.prepare_batch(
        user_email=user_email,
        device_id=device_id,
        collection_id=collection_id,
        client_sync_key=str(client_sync_key),
        emails=emails,
        window_size=window_size,
    )
