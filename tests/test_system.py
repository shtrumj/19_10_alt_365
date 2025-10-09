#!/usr/bin/env python3
"""
Test script for the 365 Email System
"""
import requests
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_URL = "http://localhost:8000"
SMTP_HOST = "localhost"
SMTP_PORT = 1025

def test_api_connection():
    """Test if the API is running"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print("❌ API health check failed")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False

def register_test_users():
    """Register test users"""
    users = [
        {
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
            "full_name": "Alice Smith"
        },
        {
            "username": "bob",
            "email": "bob@example.com", 
            "password": "password123",
            "full_name": "Bob Johnson"
        }
    ]
    
    tokens = {}
    
    for user in users:
        try:
            response = requests.post(f"{BASE_URL}/auth/register", json=user)
            if response.status_code == 200:
                print(f"✅ Registered user: {user['username']}")
                
                # Login to get token
                login_data = {
                    "username": user["username"],
                    "password": user["password"]
                }
                login_response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
                if login_response.status_code == 200:
                    token_data = login_response.json()
                    tokens[user["username"]] = token_data["access_token"]
                    print(f"✅ Logged in user: {user['username']}")
                else:
                    print(f"❌ Failed to login user: {user['username']}")
            else:
                print(f"❌ Failed to register user: {user['username']} - {response.text}")
        except Exception as e:
            print(f"❌ Error registering user {user['username']}: {e}")
    
    return tokens

def test_email_sending(tokens):
    """Test sending emails via API"""
    if "alice" not in tokens:
        print("❌ Alice not logged in, cannot test email sending")
        return
    
    headers = {"Authorization": f"Bearer {tokens['alice']}"}
    
    email_data = {
        "subject": "Test Email from API",
        "body": "This is a test email sent via the API",
        "recipient_email": "bob@example.com"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/emails/send", json=email_data, headers=headers)
        if response.status_code == 200:
            print("✅ Email sent via API")
            return True
        else:
            print(f"❌ Failed to send email via API: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending email via API: {e}")
        return False

def test_smtp_sending():
    """Test sending email via SMTP"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = "alice@example.com"
        msg['To'] = "bob@example.com"
        msg['Subject'] = "Test Email via SMTP"
        
        body = "This is a test email sent via SMTP server"
        msg.attach(MIMEText(body, 'plain'))
        
        # Send via SMTP
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg)
        
        print("✅ Email sent via SMTP")
        return True
    except Exception as e:
        print(f"❌ Error sending email via SMTP: {e}")
        return False

def test_email_retrieval(tokens):
    """Test retrieving emails"""
    if "bob" not in tokens:
        print("❌ Bob not logged in, cannot test email retrieval")
        return
    
    headers = {"Authorization": f"Bearer {tokens['bob']}"}
    
    try:
        response = requests.get(f"{BASE_URL}/emails/", headers=headers)
        if response.status_code == 200:
            emails = response.json()
            print(f"✅ Retrieved {len(emails)} emails for Bob")
            return True
        else:
            print(f"❌ Failed to retrieve emails: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error retrieving emails: {e}")
        return False

def test_owa_interface():
    """Test OWA web interface"""
    try:
        response = requests.get(f"{BASE_URL}/owa/")
        if response.status_code == 200:
            print("✅ OWA interface is accessible")
            return True
        else:
            print(f"❌ OWA interface not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error accessing OWA interface: {e}")
        return False

def test_activesync():
    """Test ActiveSync endpoints"""
    try:
        # Test ping
        response = requests.get(f"{BASE_URL}/activesync/ping")
        if response.status_code == 200:
            print("✅ ActiveSync ping successful")
        else:
            print(f"❌ ActiveSync ping failed: {response.status_code}")
        
        # Test folders
        response = requests.get(f"{BASE_URL}/activesync/folders")
        if response.status_code == 200:
            print("✅ ActiveSync folders endpoint working")
        else:
            print(f"❌ ActiveSync folders failed: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing ActiveSync: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting 365 Email System Tests")
    print("=" * 50)
    
    # Test API connection
    if not test_api_connection():
        print("❌ Cannot proceed without API connection")
        return
    
    print("\n📝 Testing User Registration and Authentication")
    tokens = register_test_users()
    
    if not tokens:
        print("❌ No users registered, cannot continue testing")
        return
    
    print("\n📧 Testing Email Functionality")
    test_email_sending(tokens)
    test_smtp_sending()
    
    # Wait a moment for emails to be processed
    time.sleep(2)
    
    test_email_retrieval(tokens)
    
    print("\n🌐 Testing Web Interface")
    test_owa_interface()
    
    print("\n📱 Testing ActiveSync")
    test_activesync()
    
    print("\n" + "=" * 50)
    print("✅ Test completed!")
    print("\n📋 Access Points:")
    print(f"  • Web Interface: {BASE_URL}/owa")
    print(f"  • API Documentation: {BASE_URL}/docs")
    print(f"  • SMTP Server: {SMTP_HOST}:{SMTP_PORT}")
    print(f"  • ActiveSync: {BASE_URL}/activesync")

if __name__ == "__main__":
    main()
