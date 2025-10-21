#!/usr/bin/env python3
"""
Cleanup script to remove user and all associated data from the database
"""
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from sqlalchemy.orm import Session

from app.database import (
    ActiveSyncDevice,
    ActiveSyncState,
    CalendarEvent,
    Email,
    User,
    get_db,
)


def cleanup_user_data(email: str):
    """Remove user and all associated data from the database"""

    print(f"Starting cleanup for user: {email}")

    # Get database session
    db = next(get_db())

    try:
        # Find the user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User {email} not found in database")
            return False

        user_id = user.id
        username = user.username

        print(f"Found user: {username} (ID: {user_id})")

        # 1. Delete ActiveSync states
        activesync_states = (
            db.query(ActiveSyncState).filter(ActiveSyncState.user_id == user_id).all()
        )
        print(f"Deleting {len(activesync_states)} ActiveSync states...")
        for state in activesync_states:
            db.delete(state)

        # 2. Delete ActiveSync devices
        activesync_devices = (
            db.query(ActiveSyncDevice).filter(ActiveSyncDevice.user_id == user_id).all()
        )
        print(f"Deleting {len(activesync_devices)} ActiveSync devices...")
        for device in activesync_devices:
            db.delete(device)

        # 3. Delete emails (both sent and received)
        sent_emails = db.query(Email).filter(Email.sender_id == user_id).all()
        received_emails = db.query(Email).filter(Email.recipient_id == user_id).all()
        print(f"Deleting {len(sent_emails)} sent emails...")
        print(f"Deleting {len(received_emails)} received emails...")

        for email in sent_emails + received_emails:
            db.delete(email)

        # 4. Delete calendar events
        # Calendar events are owned via owner_id
        calendar_events = (
            db.query(CalendarEvent).filter(CalendarEvent.owner_id == user_id).all()
        )
        print(f"Deleting {len(calendar_events)} calendar events...")
        for event in calendar_events:
            db.delete(event)

        # 5. Finally, delete the user
        print(f"Deleting user {username}...")
        db.delete(user)

        # Commit all changes
        db.commit()

        print(f"✅ Successfully cleaned up all data for user: {email}")
        print(f"   - Deleted {len(activesync_states)} ActiveSync states")
        print(f"   - Deleted {len(activesync_devices)} ActiveSync devices")
        print(f"   - Deleted {len(sent_emails)} sent emails")
        print(f"   - Deleted {len(received_emails)} received emails")
        print(f"   - Deleted {len(calendar_events)} calendar events")
        print(f"   - Deleted user account")

        return True

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def list_all_users():
    """List all users in the database"""
    db = next(get_db())
    try:
        users = db.query(User).all()
        print(f"\nCurrent users in database ({len(users)}):")
        for user in users:
            print(f"  - ID: {user.id}, Username: {user.username}, Email: {user.email}")
        return users
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up user data from database")
    parser.add_argument("--email", required=True, help="Email of user to clean up")
    parser.add_argument(
        "--list", action="store_true", help="List all users before cleanup"
    )
    parser.add_argument(
        "--confirm", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if args.list:
        list_all_users()

    if not args.confirm:
        print(
            f"\n⚠️  WARNING: This will permanently delete ALL data for user: {args.email}"
        )
        print("   This includes:")
        print("   - User account")
        print("   - All emails (sent and received)")
        print("   - All calendar events")
        print("   - All ActiveSync devices and states")
        print("   - All other associated data")

        response = input(
            "\nAre you sure you want to continue? (type 'yes' to confirm): "
        )
        if response.lower() != "yes":
            print("❌ Cleanup cancelled")
            sys.exit(0)

    success = cleanup_user_data(args.email)

    if success:
        print("\n✅ Cleanup completed successfully!")
        print("You can now re-register the user from the UI.")
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)
