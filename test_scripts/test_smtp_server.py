#!/usr/bin/env python3
"""
Test SMTP server with handler
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.smtp_server import SMTPServer25
import smtplib
from email.mime.text import MIMEText
import time

async def test_smtp_server():
    """Test SMTP server with handler"""
    try:
        print("Starting SMTP server...")
        smtp_server = SMTPServer25()
        await smtp_server.start()
        
        print("SMTP server started, waiting 2 seconds...")
        await asyncio.sleep(2)
        
        print("Sending test email...")
        # Send test email
        msg = MIMEText("Test email body")
        msg['From'] = 'shtrumj@gmail.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = 'Test Email via SMTP Server'
        
        server = smtplib.SMTP('localhost', 25)
        server.send_message(msg)
        server.quit()
        
        print("Email sent, waiting 2 seconds...")
        await asyncio.sleep(2)
        
        # Check database
        from app.database import SessionLocal, Email
        db = SessionLocal()
        try:
            emails = db.query(Email).all()
            print(f"📧 Found {len(emails)} emails in database")
            for email in emails:
                print(f"  - ID: {email.id}, Subject: {email.subject}, From: {email.external_sender}")
        finally:
            db.close()
        
        await smtp_server.stop()
        print("SMTP server stopped")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smtp_server())
