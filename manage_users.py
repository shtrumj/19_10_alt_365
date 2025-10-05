#!/usr/bin/env python3
"""
User management script for the 365 Email System
"""
import argparse
import getpass
import subprocess
import sys


def create_user(
    email: str, username: str = None, full_name: str = None, password: str = None
):
    """Create a new user in the database"""

    if not password:
        password = getpass.getpass("Enter password for the user: ")

    if not username:
        username = email.split("@")[0]

    if not full_name:
        full_name = username.title()

    create_script = f"""
from app.database import get_db, User
from app.auth import get_password_hash

db = next(get_db())
try:
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == '{email}').first()
    if existing_user:
        print(f'❌ User {email} already exists (ID: {{existing_user.id}})')
        exit(1)
    
    # Create new user
    user = User(
        username='{username}',
        email='{email}',
        full_name='{full_name}',
        hashed_password=get_password_hash('{password}')
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    print(f'✅ Created user: {{user.username}} ({{user.email}})')
    print(f'   User ID: {{user.id}}')
    print(f'   Full Name: {{user.full_name}}')
    
except Exception as e:
    print(f'❌ Error creating user: {{e}}')
    db.rollback()
    exit(1)
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
            create_script,
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
        print(f'  - ID: {user.id}, Username: {user.username}, Email: {user.email}, Full Name: {user.full_name}')
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


def delete_user(email: str):
    """Delete a user and all associated data"""

    # Import the cleanup function
    from cleanup_user_docker import run_cleanup_command

    return run_cleanup_command(email)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage users in the 365 Email System")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create user command
    create_parser = subparsers.add_parser("create", help="Create a new user")
    create_parser.add_argument("email", help="User email address")
    create_parser.add_argument("--username", help="Username (defaults to email prefix)")
    create_parser.add_argument("--full-name", help="Full name (defaults to username)")
    create_parser.add_argument(
        "--password", help="Password (will prompt if not provided)"
    )

    # List users command
    subparsers.add_parser("list", help="List all users")

    # Delete user command
    delete_parser = subparsers.add_parser(
        "delete", help="Delete a user and all associated data"
    )
    delete_parser.add_argument("email", help="Email of user to delete")

    args = parser.parse_args()

    if args.command == "create":
        success = create_user(args.email, args.username, args.full_name, args.password)
        if success:
            print("\n✅ User created successfully!")
        else:
            print("\n❌ Failed to create user!")
            sys.exit(1)
    elif args.command == "list":
        list_users()
    elif args.command == "delete":
        print(
            f"⚠️  WARNING: This will permanently delete ALL data for user: {args.email}"
        )
        response = input("Are you sure you want to continue? (type 'yes' to confirm): ")
        if response.lower() == "yes":
            success = delete_user(args.email)
            if success:
                print("\n✅ User deleted successfully!")
            else:
                print("\n❌ Failed to delete user!")
                sys.exit(1)
        else:
            print("❌ Deletion cancelled")
    else:
        parser.print_help()
