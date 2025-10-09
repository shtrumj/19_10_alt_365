#!/usr/bin/env python3
"""
Test script to check if emails are stored in the database
"""
import sqlite3
import os

def check_emails():
    """Check emails in the database"""
    print("🧪 Checking emails in database...")
    
    # Check if database exists
    db_path = "email_system.db"
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check emails table
        cursor.execute("SELECT COUNT(*) FROM emails")
        email_count = cursor.fetchone()[0]
        print(f"📧 Total emails in database: {email_count}")
        
        # Get recent emails
        cursor.execute("""
            SELECT id, subject, external_sender, external_recipient, is_external, created_at 
            FROM emails 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        emails = cursor.fetchall()
        
        print("📧 Recent emails:")
        for email in emails:
            print(f"  ID: {email[0]}, Subject: {email[1]}, From: {email[2]}, To: {email[3]}, External: {email[4]}, Created: {email[5]}")
        
        # Check users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 Total users in database: {user_count}")
        
        # Get users
        cursor.execute("SELECT id, username, email, full_name FROM users")
        users = cursor.fetchall()
        
        print("👥 Users:")
        for user in users:
            print(f"  ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Name: {user[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

if __name__ == "__main__":
    check_emails()
