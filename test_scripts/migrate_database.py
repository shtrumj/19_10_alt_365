#!/usr/bin/env python3
"""
Database migration script to add external_sender column
"""
import sqlite3
import os

def migrate_database():
    """Add external_sender column to emails table"""
    db_path = "365_email.db"
    
    if not os.path.exists(db_path):
        print("Database not found. Creating new database...")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if external_sender column exists
        cursor.execute("PRAGMA table_info(emails)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'external_sender' not in columns:
            print("Adding external_sender column to emails table...")
            cursor.execute("ALTER TABLE emails ADD COLUMN external_sender VARCHAR")
            conn.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ external_sender column already exists!")
            
        # Also make sender_id nullable if it's not already
        cursor.execute("PRAGMA table_info(emails)")
        columns_info = cursor.fetchall()
        sender_id_info = next((col for col in columns_info if col[1] == 'sender_id'), None)
        
        if sender_id_info and sender_id_info[3] == 1:  # 1 means NOT NULL
            print("Making sender_id nullable...")
            # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
            print("⚠️  Note: SQLite doesn't support changing column constraints directly.")
            print("   The new schema will be applied when the database is recreated.")
        else:
            print("✅ sender_id is already nullable!")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate_database()
