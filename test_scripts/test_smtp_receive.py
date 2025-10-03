#!/usr/bin/env python3
"""
Test SMTP server email reception
"""
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_send():
    """Send a test email to the SMTP server"""
    try:
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = 'shtrumj@gmail.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = 'Test Email from External Sender'
        
        body = "This is a test email from an external sender to test the SMTP server."
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server
        print("Connecting to SMTP server...")
        server = smtplib.SMTP('localhost', 25)
        server.set_debuglevel(1)  # Enable debug output
        
        # Send email
        print("Sending test email...")
        server.send_message(msg)
        server.quit()
        
        print("✅ Test email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error sending test email: {e}")
        return False

if __name__ == "__main__":
    print("Testing SMTP email reception...")
    test_smtp_send()
