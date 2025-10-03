"""
ActiveSync Protocol Implementation

Z-Push/Grommunio-Sync compatible implementation with:
- Spec-compliant WBXML encoding (MS-ASWBXML)
- Idempotent state machine (proper retry handling)
- Full iOS/iPhone support
"""

from .wbxml_builder import create_sync_response_wbxml, SyncBatch
from .state_machine import SyncStateStore
from .adapter import sync_prepare_batch, convert_db_email_to_dict

__all__ = [
    'create_sync_response_wbxml',
    'SyncBatch',
    'SyncStateStore',
    'sync_prepare_batch',
    'convert_db_email_to_dict',
]
