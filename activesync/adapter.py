#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adapter.py — glue from your storage rows to builder-friendly dicts.
"""

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
import os

def select_inbox_slice(all_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure each row has the fields the builder expects:
      id, subject, sender/from, recipient/to, created_at, is_read, preview/body (optional)
    """
    out: List[Dict[str, Any]] = []
    for r in all_rows:
        out.append({
            "id": r.get("id"),
            "subject": r.get("subject") or "(no subject)",
            "from": r.get("sender") or r.get("from") or "",
            "to": r.get("recipient") or r.get("to") or "",
            "created_at": r.get("created_at"),
            "is_read": bool(r.get("is_read")),
            "body": r.get("body") or r.get("preview") or "",
        })
    return out


# Legacy compatibility
def _row_to_email_dict(row: Any) -> Dict[str, Any]:
    # Accept both dict-like and attribute-like rows
    g = (row if isinstance(row, dict) else row.__dict__)
    return {
        "id": g.get("id"),
        "server_id": g.get("server_id") or g.get("id"),
        "subject": g.get("subject") or "No Subject",
        # Prefer external sender first, then related user email, then raw string
        "from": (
            g.get("external_sender")
            or (getattr(g.get("sender"), "email", None) if g.get("sender") else None)
            or g.get("from")
            or g.get("sender")
            or ""
        ),
        # Prefer external recipient first, then related user email, then raw string
        "to": (
            g.get("external_recipient")
            or (getattr(g.get("recipient"), "email", None) if g.get("recipient") else None)
            or g.get("to")
            or g.get("recipient")
            or ""
        ),
        "is_read": bool(g.get("is_read")),
        "created_at": g.get("created_at") if isinstance(g.get("created_at"), datetime) else g.get("created_at"),
        "body": g.get("body") or g.get("preview") or g.get("snippet") or "",
        # Prefer HTML body when available (various possible model field names)
        "body_html": g.get("body_html") or g.get("html_body") or g.get("html") or "",
    }


def sync_prepare_batch(
    *,
    user_email: str,
    device_id: str,
    collection_id: str,
    client_sync_key: str,
    db_emails: List[Any],
    window_size: int = 25,
) -> 'SyncBatch':
    """Legacy compatibility wrapper."""
    from .state_machine import SyncStateStore
    from .wbxml_builder import SyncBatch
    
    # One in-memory store (replace with a DB-backed implementation if needed)
    STORE = SyncStateStore()
    
    emails = [_row_to_email_dict(r) for r in db_emails]

    # Envelope-only test mode: force no Commands to verify key advancement
    if os.getenv("EAS_ENVELOPE_ONLY", "0") in ("1", "true", "True"):
        emails = []

    return STORE.prepare_batch(
        user_email=user_email,
        device_id=device_id,
        collection_id=collection_id,
        client_sync_key=str(client_sync_key),
        emails=emails,
        window_size=window_size,
    )