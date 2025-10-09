#!/usr/bin/env python3
"""
Test script to login and check emails
"""
import requests
import json

def test_login_and_emails():
    """Test login and email access"""
    
    base_url = "https://localhost:443"
    
    # Disable SSL verification for testing
    session = requests.Session()
    session.verify = False
    
    try:
        # Login with the reset password
        print("Attempting to login...")
        login_data = {
            "username": "yonatan",
            "password": "password123"
        }
        
        # Try API login
        login_response = session.post(f"{base_url}/auth/login", json=login_data)
        print(f"Login response status: {login_response.status_code}")
        
        if login_response.status_code == 200:
            try:
                token_data = login_response.json()
                print("Login successful! Got token.")
                
                # Set the token in session
                session.headers.update({'Authorization': f"Bearer {token_data.get('access_token')}"})
                
                # Try to get emails
                print("Fetching emails...")
                emails_response = session.get(f"{base_url}/emails/?limit=10")
                print(f"Emails response status: {emails_response.status_code}")
                
                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    print(f"Found {len(emails)} emails:")
                    for i, email in enumerate(emails, 1):
                        sender = email.get('sender', {}).get('email', 'Unknown') if email.get('sender') else email.get('external_sender', 'External')
                        recipient = email.get('recipient', {}).get('email', 'Unknown') if email.get('recipient') else email.get('external_recipient', 'External')
                        print(f"  {i}. From: {sender}, To: {recipient}, Subject: {email.get('subject', 'No subject')}")
                    return True
                else:
                    print(f"Failed to get emails: {emails_response.text}")
                    return False
            except json.JSONDecodeError:
                print("Login response is not JSON - might be HTML redirect")
                print(f"Response: {login_response.text[:200]}...")
                return False
        else:
            print(f"Login failed: {login_response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing login and email access...")
    success = test_login_and_emails()
    if success:
        print("✅ Login and email test successful!")
    else:
        print("❌ Login and email test failed!")
