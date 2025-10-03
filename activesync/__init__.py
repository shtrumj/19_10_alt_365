"""
ActiveSync Protocol Implementation

Z-Push/Grommunio-Sync compatible implementation with:
- Spec-compliant WBXML encoding (MS-ASWBXML)
- Strict InvalidSyncKey handling (MS-ASCMD Status=3)
- Idempotent state machine (proper retry handling)
- Full iOS/iPhone support
"""

from .wbxml_builder import (
    build_sync_response, 
    build_foldersync_no_changes,
    extract_synckey_and_collection,
    create_sync_response_wbxml, 
    create_invalid_synckey_response_wbxml, 
    SyncBatch
)
from .state_machine import SyncStateStore
from .adapter import sync_prepare_batch, select_inbox_slice

__all__ = [
    'build_sync_response',
    'build_foldersync_no_changes',
    'extract_synckey_and_collection',
    'create_sync_response_wbxml',
    'create_invalid_synckey_response_wbxml',
    'SyncBatch',
    'SyncStateStore',
    'sync_prepare_batch',
    'select_inbox_slice',
]