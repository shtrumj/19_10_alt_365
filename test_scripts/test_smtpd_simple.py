#!/usr/bin/env python3
"""
Test script to verify smtpd.SMTPServer methods
"""
import smtpd
import threading
import time

class TestHandler(smtpd.SMTPServer):
    def __init__(self, localaddr, remoteaddr=None):
        super().__init__(localaddr, remoteaddr)
        print("🔧 TestHandler initialized")
    
    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        print(f"📧 Email received from {mailfrom} to {rcpttos}")
        print(f"📧 Data: {data[:100]}...")
        return "250 OK"

def test_smtpd():
    """Test smtpd.SMTPServer"""
    print("🧪 Testing smtpd.SMTPServer...")
    
    try:
        # Create server
        server = TestHandler(('localhost', 2525))
        print("✅ Server created")
        
        # Check available methods
        print(f"🔍 Available methods: {[m for m in dir(server) if not m.startswith('_')]}")
        
        # Try to start server
        print("🚀 Starting server...")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        print("✅ Server started on localhost:2525")
        print("⏳ Waiting for 10 seconds...")
        time.sleep(10)
        
        server.close()
        print("✅ Test completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smtpd()
