#!/usr/bin/env python3
"""
Docker-based cleanup script to remove user and all associated data from the database
This script runs inside the Docker container where it has access to the database
"""
import argparse
import subprocess
import sys


def run_cleanup_command(email: str):
    """Run the cleanup command inside the Docker container"""

    cleanup_script = f"""
from app.database import get_db, User, ActiveSyncDevice, ActiveSyncState, Email, CalendarEvent
from sqlalchemy.orm import Session

# Get database session
db = next(get_db())

try:
    # Find the user
    user = db.query(User).filter(User.email == '{email}').first()
    if not user:
        print('❌ User {email} not found in database')
        exit(1)
    
    user_id = user.id
    username = user.username
    
    print(f'Found user: {{username}} (ID: {{user_id}})')
    
    # 1. Delete ActiveSync states
    activesync_states = db.query(ActiveSyncState).filter(ActiveSyncState.user_id == user_id).all()
    print(f'Deleting {{len(activesync_states)}} ActiveSync states...')
    for state in activesync_states:
        db.delete(state)
    
    # 2. Delete ActiveSync devices
    activesync_devices = db.query(ActiveSyncDevice).filter(ActiveSyncDevice.user_id == user_id).all()
    print(f'Deleting {{len(activesync_devices)}} ActiveSync devices...')
    for device in activesync_devices:
        db.delete(device)
    
    # 3. Delete emails (both sent and received)
    sent_emails = db.query(Email).filter(Email.sender_id == user_id).all()
    received_emails = db.query(Email).filter(Email.recipient_id == user_id).all()
    print(f'Deleting {{len(sent_emails)}} sent emails...')
    print(f'Deleting {{len(received_emails)}} received emails...')
    
    for email in sent_emails + received_emails:
        db.delete(email)
    
    # 4. Delete calendar events (using owner_id)
    calendar_events = db.query(CalendarEvent).filter(CalendarEvent.owner_id == user_id).all()
    print(f'Deleting {{len(calendar_events)}} calendar events...')
    for event in calendar_events:
        db.delete(event)
    
    # 5. Finally, delete the user
    print(f'Deleting user {{username}}...')
    db.delete(user)
    
    # Commit all changes
    db.commit()
    
    print(f'✅ Successfully cleaned up all data for user: {email}')
    print(f'   - Deleted {{len(activesync_states)}} ActiveSync states')
    print(f'   - Deleted {{len(activesync_devices)}} ActiveSync devices')
    print(f'   - Deleted {{len(sent_emails)}} sent emails')
    print(f'   - Deleted {{len(received_emails)}} received emails')
    print(f'   - Deleted {{len(calendar_events)}} calendar events')
    print(f'   - Deleted user account')
    
except Exception as e:
    print(f'❌ Error during cleanup: {{e}}')
    db.rollback()
    exit(1)
finally:
    db.close()
"""

    # Run the cleanup script inside the Docker container
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "email-system",
            "python",
            "-c",
            cleanup_script,
        ],
        cwd="/Users/jonathanshtrum/Dev/4_09_365_alt",
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    return result.returncode == 0


def list_users():
    """List all users in the database"""

    list_script = """
from app.database import get_db, User

db = next(get_db())
try:
    users = db.query(User).all()
    print(f'Current users in database ({len(users)}):')
    for user in users:
        print(f'  - ID: {user.id}, Username: {user.username}, Email: {user.email}')
finally:
    db.close()
"""

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "email-system",
            "python",
            "-c",
            list_script,
        ],
        cwd="/Users/jonathanshtrum/Dev/4_09_365_alt",
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up user data from database")
    parser.add_argument("--email", help="Email of user to clean up")
    parser.add_argument("--list", action="store_true", help="List all users")

    args = parser.parse_args()

    if args.list:
        list_users()
    elif args.email:
        print(f"Cleaning up user: {args.email}")
        success = run_cleanup_command(args.email)
        if success:
            print("\n✅ Cleanup completed successfully!")
            print("You can now re-register the user from the UI.")
        else:
            print("\n❌ Cleanup failed!")
            sys.exit(1)
    else:
        parser.print_help()
