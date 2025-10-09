#!/usr/bin/env python3
"""
Test SMTP server without TLS
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_simple():
    """Test SMTP server without TLS"""
    print("🧪 Testing SMTP server (no TLS)...")
    
    try:
        # Connect to SMTP server
        print("1. Connecting to SMTP server...")
        server = smtplib.SMTP('localhost', 25)
        print("   ✅ Connected to SMTP server")
        
        # Send EHLO command
        print("2. Sending EHLO command...")
        server.ehlo()
        print("   ✅ EHLO successful")
        
        # Send test email
        print("3. Sending test email...")
        msg = MIMEMultipart()
        msg['From'] = 'test@example.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = 'Simple SMTP Test Email'
        
        body = 'This is a test email sent without TLS encryption.'
        msg.attach(MIMEText(body, 'plain'))
        
        # Send the email
        text = msg.as_string()
        server.sendmail('test@example.com', 'yonatan@shtrum.com', text)
        print("   ✅ Test email sent successfully")
        
        # Quit
        print("4. Quitting connection...")
        server.quit()
        print("   ✅ Connection closed")
        
        print("\n🎉 Simple SMTP test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_smtp_simple()
