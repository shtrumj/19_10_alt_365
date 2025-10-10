#!/usr/bin/env python3
"""
MAPI/HTTP Database Migration Script

Creates the necessary tables for MAPI/HTTP support:
- mapi_sessions
- mapi_objects
- mapi_subscriptions
- mapi_sync_states

Run this inside the Docker container:
  docker exec -it <container> python3 migrate_mapi_tables.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import inspect

from app.database import Base, SessionLocal, engine


def check_table_exists(table_name):
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate():
    """Run the migration."""
    print("=" * 70)
    print("MAPI/HTTP Database Migration")
    print("=" * 70)
    print()

    # Check which tables exist
    tables_to_create = [
        "mapi_sessions",
        "mapi_objects",
        "mapi_subscriptions",
        "mapi_sync_states",
    ]

    existing_tables = []
    missing_tables = []

    for table in tables_to_create:
        if check_table_exists(table):
            existing_tables.append(table)
        else:
            missing_tables.append(table)

    if existing_tables:
        print("✅ Existing MAPI tables:")
        for table in existing_tables:
            print(f"   - {table}")
        print()

    if missing_tables:
        print("🔨 Creating missing MAPI tables:")
        for table in missing_tables:
            print(f"   - {table}")
        print()

        # Create all tables
        print("Running Base.metadata.create_all()...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully!")
        print()
    else:
        print("✅ All MAPI tables already exist - nothing to do!")
        print()

    # Verify
    print("Verification:")
    for table in tables_to_create:
        exists = check_table_exists(table)
        status = "✅" if exists else "❌"
        print(f"   {status} {table}: {'exists' if exists else 'MISSING'}")
    print()

    print("=" * 70)
    print("Migration Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Restart the Docker container (if needed)")
    print("  2. Configure Outlook Desktop to use MAPI/HTTP")
    print("  3. Monitor logs: docker logs -f <container>")
    print()


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
