#!/usr/bin/env python3
"""
Test TLS support in SMTP server
"""
import smtplib
import ssl
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_tls():
    """Test SMTP server with TLS support"""
    print("🧪 Testing SMTP server with TLS support...")
    
    try:
        # Connect to SMTP server
        print("1. Connecting to SMTP server...")
        server = smtplib.SMTP('localhost', 25)
        print("   ✅ Connected to SMTP server")
        
        # Send EHLO command
        print("2. Sending EHLO command...")
        server.ehlo()
        print("   ✅ EHLO successful")
        
        # Check if STARTTLS is supported
        print("3. Checking STARTTLS support...")
        if server.has_extn('STARTTLS'):
            print("   ✅ STARTTLS is supported")
            
            # Start TLS
            print("4. Starting TLS...")
            server.starttls()
            print("   ✅ TLS started successfully")
            
            # Send EHLO again after TLS
            print("5. Sending EHLO after TLS...")
            server.ehlo()
            print("   ✅ EHLO after TLS successful")
            
        else:
            print("   ❌ STARTTLS not supported")
            return False
        
        # Send test email
        print("6. Sending test email...")
        msg = MIMEMultipart()
        msg['From'] = 'test@example.com'
        msg['To'] = 'yonatan@shtrum.com'
        msg['Subject'] = 'TLS Test Email'
        
        body = 'This is a test email sent with TLS encryption.'
        msg.attach(MIMEText(body, 'plain'))
        
        # Send the email
        text = msg.as_string()
        server.sendmail('test@example.com', 'yonatan@shtrum.com', text)
        print("   ✅ Test email sent successfully")
        
        # Quit
        print("7. Quitting connection...")
        server.quit()
        print("   ✅ Connection closed")
        
        print("\n🎉 TLS SMTP test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during TLS test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_smtp_tls()
