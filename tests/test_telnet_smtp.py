#!/usr/bin/env python3
"""
Test SMTP server using telnet-like connection
"""
import socket
import time

def test_smtp_telnet(host, port):
    """Test SMTP server with telnet-like connection"""
    try:
        print(f"Connecting to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        
        # Read the welcome message
        response = sock.recv(1024).decode('utf-8')
        print(f"Server response: {response.strip()}")
        
        # Send HELO command
        sock.send(b"HELO test.com\r\n")
        response = sock.recv(1024).decode('utf-8')
        print(f"HELO response: {response.strip()}")
        
        # Send QUIT command
        sock.send(b"QUIT\r\n")
        response = sock.recv(1024).decode('utf-8')
        print(f"QUIT response: {response.strip()}")
        
        sock.close()
        print("✅ SMTP server is working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    # Test localhost
    print("Testing localhost:25...")
    test_smtp_telnet("127.0.0.1", 25)
    
    print("\n" + "="*50 + "\n")
    
    # Test all interfaces
    print("Testing 0.0.0.0:25...")
    test_smtp_telnet("0.0.0.0", 25)
