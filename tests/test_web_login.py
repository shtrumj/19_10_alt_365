#!/usr/bin/env python3
"""
Test script to login via web form and check emails
"""
import requests
import json
from bs4 import BeautifulSoup

def test_web_login():
    """Test web login and email access"""
    
    base_url = "https://localhost:443"
    
    # Disable SSL verification for testing
    session = requests.Session()
    session.verify = False
    
    try:
        # First, get the login page to get any CSRF tokens
        print("Getting login page...")
        login_page = session.get(f"{base_url}/auth/login")
        print(f"Login page status: {login_page.status_code}")
        
        # Parse the login page
        soup = BeautifulSoup(login_page.text, 'html.parser')
        form = soup.find('form')
        if not form:
            print("No login form found")
            return False
        
        # Login with form data
        print("Attempting web login...")
        login_data = {
            "username": "yonatan",
            "password": "Gib$0n579!"
        }
        
        # Try web login (form submission)
        login_response = session.post(f"{base_url}/auth/login", data=login_data)
        print(f"Login response status: {login_response.status_code}")
        print(f"Login response URL: {login_response.url}")
        
        # Check if we got redirected (successful login)
        if "owa" in login_response.url or login_response.status_code == 302:
            print("Login successful! Redirected to OWA.")
            
            # Try to access the OWA inbox
            print("Accessing OWA inbox...")
            inbox_response = session.get(f"{base_url}/owa/inbox")
            print(f"Inbox response status: {inbox_response.status_code}")
            
            if inbox_response.status_code == 200:
                # Parse the inbox page to look for emails
                inbox_soup = BeautifulSoup(inbox_response.text, 'html.parser')
                
                # Look for email elements
                email_elements = inbox_soup.find_all(['div', 'tr'], class_=lambda x: x and ('email' in x.lower() or 'message' in x.lower()))
                print(f"Found {len(email_elements)} potential email elements")
                
                # Look for error messages
                error_elements = inbox_soup.find_all(text=lambda x: x and 'error' in x.lower())
                if error_elements:
                    print("Error messages found:")
                    for error in error_elements[:3]:  # Show first 3 errors
                        print(f"  - {error.strip()}")
                
                # Look for email count or statistics
                stats_elements = inbox_soup.find_all(text=lambda x: x and any(word in x.lower() for word in ['email', 'message', 'inbox', 'total']))
                if stats_elements:
                    print("Email-related text found:")
                    for stat in stats_elements[:5]:  # Show first 5
                        print(f"  - {stat.strip()}")
                
                return True
            else:
                print(f"Failed to access inbox: {inbox_response.text[:200]}...")
                return False
        else:
            print(f"Login failed or not redirected: {login_response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing web login and email access...")
    success = test_web_login()
    if success:
        print("✅ Web login and email test successful!")
    else:
        print("❌ Web login and email test failed!")
