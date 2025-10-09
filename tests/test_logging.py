#!/usr/bin/env python3
"""
Test SMTP logging system
"""
import smtplib
from email.mime.text import MIMEText
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_smtp_logging():
    """Test SMTP logging by sending an email"""
    try:
        print("🧪 Testing SMTP logging system...")
        
        # Create test email with timestamp
        timestamp = int(time.time())
        msg = MIMEText(f"Test email body at {timestamp}")
        msg['From'] = 'shtrumj@gmail.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = f'SMTP Logging Test {timestamp}'
        
        print(f"📧 Sending test email: {msg['Subject']}")
        
        # Send email
        server = smtplib.SMTP('localhost', 25)
        server.send_message(msg)
        server.quit()
        
        print("✅ Email sent successfully!")
        
        # Wait a moment for processing
        time.sleep(2)
        
        # Check logs
        print("\n📋 Checking logs...")
        log_files = [
            "logs/internal_smtp.log",
            "logs/email_processing.log", 
            "logs/smtp_connections.log",
            "logs/smtp_errors.log"
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                print(f"\n📄 {log_file}:")
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Show last 10 lines
                    for line in lines[-10:]:
                        print(f"  {line.strip()}")
            else:
                print(f"❌ {log_file} not found")
        
        # Check database
        print("\n📊 Checking database...")
        from app.database import SessionLocal, Email
        db = SessionLocal()
        try:
            emails = db.query(Email).order_by(Email.created_at.desc()).all()
            print(f"📧 Found {len(emails)} emails in database")
            for i, email in enumerate(emails[:3]):
                print(f"  {i+1}. ID: {email.id}, Subject: {email.subject}, From: {email.external_sender}, Created: {email.created_at}")
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smtp_logging()
