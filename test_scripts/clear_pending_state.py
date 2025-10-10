#!/usr/bin/env python3
"""Clear pending state to force fresh WBXML build with element order fix"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db
from app.models import ActiveSyncState


def clear_pending_state():
    db = next(get_db())

    # Device ID from logs
    device_id = "B06D62AD4C9F4DEE9A21DFAFC9849BA6"
    collection_id = "1"  # Inbox

    state = (
        db.query(ActiveSyncState)
        .filter_by(device_id=device_id, collection_id=collection_id)
        .first()
    )

    if state:
        print(f"Current state:")
        print(f"  sync_key: {state.sync_key}")
        print(f"  pending_sync_key: {state.pending_sync_key}")
        print(f"  pending_item_ids: {state.pending_item_ids}")
        print(f"  last_synced_email_id: {state.last_synced_email_id}")
        print("")

        # Clear ONLY the pending cache, keep sync state
        state.pending_sync_key = None
        state.pending_item_ids = None
        state.pending_max_email_id = None

        db.commit()

        print(f"✅ Cleared pending state for device {device_id}")
        print(f"   sync_key remains: {state.sync_key}")
        print(f"   Next Sync request will rebuild WBXML with CORRECT element order")
        return True
    else:
        print(f"❌ No state found for device {device_id}")
        return False


if __name__ == "__main__":
    success = clear_pending_state()
    sys.exit(0 if success else 1)
