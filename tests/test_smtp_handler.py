#!/usr/bin/env python3
"""
Test SMTP handler directly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.smtp_server import EmailHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io

def test_smtp_handler():
    """Test the SMTP handler directly"""
    try:
        print("Testing SMTP handler...")
        
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = 'shtrumj@gmail.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = 'Test Email from External Sender'
        
        body = "This is a test email from an external sender to test the SMTP server."
        msg.attach(MIMEText(body, 'plain'))
        
        # Convert to bytes
        email_bytes = msg.as_bytes()
        print(f"Email bytes length: {len(email_bytes)}")
        
        # Create handler and test
        handler = EmailHandler()
        print("Handler created successfully")
        
        # Test the handler
        print("Calling handle_message...")
        handler.handle_message(email_bytes)
        print("✅ Handler called successfully!")
        
        # Check database
        from app.database import SessionLocal, Email
        db = SessionLocal()
        try:
            emails = db.query(Email).all()
            print(f"📧 Found {len(emails)} emails in database after test")
            for email in emails:
                print(f"  - ID: {email.id}, Subject: {email.subject}, From: {email.external_sender}, To: {email.recipient_id}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error testing SMTP handler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smtp_handler()
