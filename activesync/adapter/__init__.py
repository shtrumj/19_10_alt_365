#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ActiveSync adapter — glue from storage rows to builder-friendly dicts.

This package provides compatibility exports expected by imports like:
    from activesync.adapter import sync_prepare_batch
"""

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime
import os


def select_inbox_slice(all_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize rows to the fields expected by the WBXML builder:
      id, subject, from, to, created_at, is_read, body
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


def _row_to_email_dict(row: Any) -> Dict[str, Any]:
    """Accept both dict-like and attribute-like ORM rows and normalize."""
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


# CRITICAL: Single global state machine instance (persists across requests)
from ..state_machine import SyncStateStore
_GLOBAL_STORE = SyncStateStore()


def sync_prepare_batch(
    *,
    user_email: str,
    device_id: str,
    collection_id: str,
    client_sync_key: str,
    db_emails: List[Any],
    window_size: int = 25,
) -> 'SyncBatch':
    """Compatibility wrapper feeding the state machine with normalized emails."""
    from ..wbxml_builder import SyncBatch

    emails = [_row_to_email_dict(r) for r in db_emails]

    # Envelope-only test mode: force no Commands to verify key advancement
    if os.getenv("EAS_ENVELOPE_ONLY", "0") in ("1", "true", "True"):
        emails = []

    return _GLOBAL_STORE.prepare_batch(
        user_email=user_email,
        device_id=device_id,
        collection_id=collection_id,
        client_sync_key=str(client_sync_key),
        emails=emails,
        window_size=window_size,
    )


def convert_db_email_to_dict(row: Any) -> Dict[str, Any]:
    """Legacy alias used by older code paths."""
    return _row_to_email_dict(row)


__all__ = [
    "select_inbox_slice",
    "sync_prepare_batch",
    "convert_db_email_to_dict",
]

