#!/usr/bin/env python3
"""
Test SMTP connection to the server
"""
import socket
import sys

def test_smtp_connection(host, port):
    """Test if SMTP server is listening on the specified host and port"""
    try:
        print(f"Testing connection to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ SUCCESS: SMTP server is listening on {host}:{port}")
            return True
        else:
            print(f"❌ FAILED: Cannot connect to {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    # Test localhost
    test_smtp_connection("127.0.0.1", 25)
    
    # Test all interfaces (if you know your IP)
    # Replace with your actual IP address
    test_smtp_connection("0.0.0.0", 25)
