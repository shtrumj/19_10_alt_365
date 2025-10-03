#!/usr/bin/env python3
"""
ActiveSync State Reset Utility

Based on Z-Push's z-push-admin tool functionality for device state management.
This script properly resets ActiveSync state to allow fresh synchronization.

Usage:
    python reset_activesync_state.py --user <email> --device <device_id>
    python reset_activesync_state.py --user <email> --all-devices
    python reset_activesync_state.py --all  # Reset ALL state (dangerous!)
"""

import sys
import argparse
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, ActiveSyncState, User
from sqlalchemy import func


def reset_device_state(db, user_email: str, device_id: str):
    """
    Reset ActiveSync state for a specific user and device.
    
    This is equivalent to Z-Push's:
        z-push-admin -a remove -d DEVICE_ID
    
    Args:
        db: Database session
        user_email: User's email address
        device_id: Device identifier
    """
    # Find user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        print(f"❌ User not found: {user_email}")
        return False
    
    # Find and delete state
    states = db.query(ActiveSyncState).filter(
        ActiveSyncState.user_id == user.id,
        ActiveSyncState.device_id == device_id
    ).all()
    
    if not states:
        print(f"⚠️  No state found for user '{user_email}' device '{device_id}'")
        return False
    
    count = len(states)
    for state in states:
        print(f"🗑️  Deleting state: collection_id={state.collection_id}, sync_key={state.sync_key}")
        db.delete(state)
    
    db.commit()
    print(f"✅ Deleted {count} state record(s) for device '{device_id}'")
    print(f"📱 Device will start fresh from SyncKey=0 on next connect")
    return True


def reset_user_devices(db, user_email: str):
    """
    Reset ActiveSync state for ALL devices of a specific user.
    
    Args:
        db: Database session
        user_email: User's email address
    """
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        print(f"❌ User not found: {user_email}")
        return False
    
    states = db.query(ActiveSyncState).filter(
        ActiveSyncState.user_id == user.id
    ).all()
    
    if not states:
        print(f"⚠️  No ActiveSync state found for user '{user_email}'")
        return False
    
    devices = set(s.device_id for s in states)
    count = len(states)
    
    for state in states:
        db.delete(state)
    
    db.commit()
    print(f"✅ Deleted {count} state record(s) for {len(devices)} device(s)")
    print(f"   Devices: {', '.join(devices)}")
    print(f"📱 All devices will start fresh from SyncKey=0")
    return True


def reset_all_state(db):
    """
    Reset ALL ActiveSync state for ALL users and devices.
    
    ⚠️  DANGEROUS! Use only for testing/development.
    
    Args:
        db: Database session
    """
    count = db.query(ActiveSyncState).count()
    
    if count == 0:
        print("ℹ️  No ActiveSync state to delete")
        return True
    
    print(f"⚠️  WARNING: About to delete {count} state record(s)")
    confirm = input("Type 'YES' to confirm: ")
    
    if confirm != "YES":
        print("❌ Aborted")
        return False
    
    db.query(ActiveSyncState).delete()
    db.commit()
    
    print(f"✅ Deleted ALL {count} ActiveSync state record(s)")
    print(f"📱 ALL devices will start fresh from SyncKey=0")
    return True


def list_states(db, user_email: str = None):
    """
    List ActiveSync states (like z-push-admin -a list)
    
    Args:
        db: Database session
        user_email: Optional user filter
    """
    query = db.query(ActiveSyncState, User).join(User)
    
    if user_email:
        query = query.filter(User.email == user_email)
    
    states = query.all()
    
    if not states:
        print("ℹ️  No ActiveSync states found")
        return
    
    print("\n📊 ActiveSync States:")
    print("=" * 100)
    print(f"{'User':<25} {'Device ID':<30} {'Collection':<10} {'SyncKey':<10} {'Last Sync'}")
    print("=" * 100)
    
    for state, user in states:
        sync_key = state.sync_key
        if state.pending_sync_key:
            sync_key = f"{sync_key} (pending: {state.pending_sync_key})"
        
        print(f"{user.email:<25} {state.device_id:<30} {state.collection_id:<10} {sync_key:<10} {state.last_sync}")
    
    print("=" * 100)
    print(f"Total: {len(states)} state(s)")


def main():
    parser = argparse.ArgumentParser(
        description="ActiveSync State Reset Utility (Z-Push-style)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all states
  python reset_activesync_state.py --list
  
  # List states for specific user
  python reset_activesync_state.py --list --user yonatan@shtrum.com
  
  # Reset specific device
  python reset_activesync_state.py --user yonatan@shtrum.com --device KO090MSD656QV68VR4UUD92RA4
  
  # Reset all devices for user
  python reset_activesync_state.py --user yonatan@shtrum.com --all-devices
  
  # Reset ALL state (dangerous!)
  python reset_activesync_state.py --all
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true", help="List ActiveSync states")
    parser.add_argument("--user", "-u", help="User email address")
    parser.add_argument("--device", "-d", help="Device ID")
    parser.add_argument("--all-devices", action="store_true", help="Reset all devices for user")
    parser.add_argument("--all", action="store_true", help="Reset ALL state (dangerous!)")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    
    try:
        if args.list:
            list_states(db, args.user)
        
        elif args.all:
            reset_all_state(db)
        
        elif args.user and args.all_devices:
            reset_user_devices(db, args.user)
        
        elif args.user and args.device:
            reset_device_state(db, args.user, args.device)
        
        else:
            parser.print_help()
            return 1
        
        return 0
    
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

