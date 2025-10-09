#!/usr/bin/env python3
"""
Test sending a new email and checking if it's received
"""
import smtplib
from email.mime.text import MIMEText
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_new_email():
    """Send a new email and check if it's received"""
    try:
        print("Sending new test email...")
        
        # Create new email with timestamp
        timestamp = int(time.time())
        msg = MIMEText(f"Test email body at {timestamp}")
        msg['From'] = 'shtrumj@gmail.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = f'New Test Email {timestamp}'
        
        # Send email
        server = smtplib.SMTP('localhost', 25)
        server.send_message(msg)
        server.quit()
        
        print("Email sent successfully!")
        
        # Wait a moment
        time.sleep(1)
        
        # Check database
        from app.database import SessionLocal, Email
        db = SessionLocal()
        try:
            emails = db.query(Email).order_by(Email.created_at.desc()).all()
            print(f"📧 Found {len(emails)} emails in database")
            for i, email in enumerate(emails[:3]):  # Show last 3 emails
                print(f"  {i+1}. ID: {email.id}, Subject: {email.subject}, Created: {email.created_at}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_new_email()
