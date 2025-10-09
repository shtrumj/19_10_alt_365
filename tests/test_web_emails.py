#!/usr/bin/env python3
"""
Test script to check emails via web interface with proper authentication
"""
import requests
import json

def test_web_emails():
    """Test accessing emails through the web interface"""
    
    base_url = "https://localhost:443"
    
    # Disable SSL verification for testing
    session = requests.Session()
    session.verify = False
    
    try:
        # First, try to login
        print("Attempting to login...")
        login_data = {
            "username": "yonatan",
            "password": "Gib$0n579!"  # This should be the correct password
        }
        
        # Try API login
        login_response = session.post(f"{base_url}/auth/login", json=login_data)
        print(f"Login response status: {login_response.status_code}")
        
        if login_response.status_code == 200:
            print("Login successful!")
            token_data = login_response.json()
            print(f"Token received: {token_data.get('access_token', 'No token')[:20]}...")
            
            # Set the token in session
            session.headers.update({'Authorization': f"Bearer {token_data.get('access_token')}"})
            
            # Try to get emails
            print("Fetching emails...")
            emails_response = session.get(f"{base_url}/emails/?limit=5")
            print(f"Emails response status: {emails_response.status_code}")
            
            if emails_response.status_code == 200:
                emails = emails_response.json()
                print(f"Found {len(emails)} emails:")
                for email in emails:
                    print(f"  - From: {email.get('sender', 'Unknown')}, Subject: {email.get('subject', 'No subject')}")
                return True
            else:
                print(f"Failed to get emails: {emails_response.text}")
                return False
        else:
            print(f"Login failed: {login_response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing web email access...")
    success = test_web_emails()
    if success:
        print("✅ Web email test successful!")
    else:
        print("❌ Web email test failed!")
