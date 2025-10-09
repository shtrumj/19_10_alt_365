#!/usr/bin/env python3
"""
Debug script to check login response
"""
import requests
import json

def debug_login():
    """Debug the login response"""
    
    base_url = "https://localhost:443"
    
    # Disable SSL verification for testing
    session = requests.Session()
    session.verify = False
    
    try:
        # Try to login
        print("Attempting to login...")
        login_data = {
            "username": "yonatan",
            "password": "Gib$0n579!"
        }
        
        # Try API login
        login_response = session.post(f"{base_url}/auth/login", json=login_data)
        print(f"Login response status: {login_response.status_code}")
        print(f"Login response headers: {dict(login_response.headers)}")
        print(f"Login response text: {login_response.text}")
        
        if login_response.status_code == 200:
            try:
                token_data = login_response.json()
                print(f"Token data: {token_data}")
            except:
                print("Response is not JSON, checking if it's HTML...")
                if "html" in login_response.text.lower():
                    print("Response is HTML - this might be a redirect to login page")
                else:
                    print("Response is neither JSON nor HTML")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_login()
