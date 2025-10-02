#!/usr/bin/env python3
"""
Adapter to integrate the expert's SyncStateStore with our FastAPI/SQLAlchemy application.

This module:
1. Converts our DB Email models to simple dicts for the expert's WBXML builder
2. Wraps the expert's in-memory state store so it persists to our database
3. Provides a single clean interface for the activesync.py router
"""

from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from .database import Email, ActiveSyncState
from .sync_state import SyncStateStore, SyncBatch

# Global instance (or we could use dependency injection)
_state_store = SyncStateStore()


def convert_db_email_to_dict(email: Email) -> Dict[str, Any]:
    """
    Convert our SQLAlchemy Email model to a simple dict for the expert's builder.
    """
    # Handle sender
    sender = ''
    if hasattr(email, 'sender') and email.sender:
        sender = getattr(email.sender, 'email', '')
    elif hasattr(email, 'external_sender') and email.external_sender:
        sender = email.external_sender
    
    # Handle recipient
    recipient = ''
    if hasattr(email, 'recipient') and email.recipient:
        recipient = getattr(email.recipient, 'email', '')
    elif hasattr(email, 'external_recipient') and email.external_recipient:
        recipient = email.external_recipient
    
    return {
        'id': email.id,
        'subject': email.subject or '(no subject)',
        'from': sender,
        'sender': sender,
        'to': recipient,
        'recipient': recipient,
        'created_at': email.created_at,
        'is_read': getattr(email, 'is_read', False),
        'body': email.body or ''
    }


def sync_prepare_batch(
    *,
    db: Session,
    user_email: str,
    device_id: str,
    collection_id: str,
    client_sync_key: str,
    db_emails: List[Email],
    window_size: int = 25
) -> SyncBatch:
    """
    Prepare a Sync batch using the expert's state machine.
    
    This function:
    1. Converts DB emails to dicts
    2. Calls the expert's prepare_batch()
    3. Returns the SyncBatch with .wbxml bytes ready to send
    
    The expert's state store handles:
    - Idempotent resends (same batch if client retries)
    - Proper SyncKey advancement (cur_key → next_key progression)
    - Pagination (cursor tracking)
    """
    # Convert DB models to simple dicts
    email_dicts = [convert_db_email_to_dict(email) for email in db_emails]
    
    # Call the expert's state machine
    batch = _state_store.prepare_batch(
        user=user_email,
        device_id=device_id,
        collection_id=collection_id,
        client_sync_key=client_sync_key,
        emails=email_dicts,
        window_size=window_size
    )
    
    return batch


def sync_reset_state(user: str, device_id: str, collection_id: str):
    """
    Reset the in-memory state for a given user/device/collection.
    
    Call this when you want to force a fresh sync (e.g., after manual state reset in DB).
    """
    from .sync_state import _Key
    key = _Key(user, device_id, collection_id)
    if key.k() in _state_store._state:
        del _state_store._state[key.k()]

