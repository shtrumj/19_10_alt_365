#!/usr/bin/env python3
"""
Test script to send an email to the SMTP server
"""
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_send():
    """Test sending an email to the local SMTP server"""
    
    # Email details
    sender = "test@example.com"
    recipient = "yonatan@shtrum.com"  # This should be a user in our system
    subject = "Test Email from External"
    body = "This is a test email to verify SMTP reception."
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to SMTP server
        print(f"Connecting to localhost:25...")
        server = smtplib.SMTP('localhost', 25)
        print("Connected successfully!")
        
        # Send email
        print(f"Sending email from {sender} to {recipient}...")
        server.send_message(msg)
        print("Email sent successfully!")
        
        server.quit()
        print("SMTP connection closed.")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing SMTP email sending...")
    success = test_smtp_send()
    if success:
        print("✅ SMTP test successful!")
    else:
        print("❌ SMTP test failed!")
