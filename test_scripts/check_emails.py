#!/usr/bin/env python3
"""
Check received emails in the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, Email, User
from sqlalchemy import desc

def check_emails():
    """Check all emails in the database"""
    db = SessionLocal()
    try:
        # Get all emails
        emails = db.query(Email).order_by(desc(Email.created_at)).all()
        
        print(f"📧 Found {len(emails)} emails in database:")
        print("=" * 80)
        
        for email in emails:
            sender_info = f"User ID: {email.sender_id}" if email.sender_id else f"External: {email.external_sender}"
            recipient_info = f"User ID: {email.recipient_id}" if email.recipient_id else f"External: {email.external_recipient}"
            
            print(f"ID: {email.id}")
            print(f"Subject: {email.subject}")
            print(f"From: {sender_info}")
            print(f"To: {recipient_info}")
            print(f"External: {email.is_external}")
            print(f"Created: {email.created_at}")
            print(f"Read: {email.is_read}")
            print("-" * 40)
        
        # Get all users
        users = db.query(User).all()
        print(f"\n👥 Found {len(users)} users in database:")
        for user in users:
            print(f"ID: {user.id}, Email: {user.email}, Name: {user.full_name}")
            
    except Exception as e:
        print(f"❌ Error checking emails: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_emails()
