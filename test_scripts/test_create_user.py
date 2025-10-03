#!/usr/bin/env python3
"""
Test script to create a new user for testing
"""
import requests
import json

def create_test_user():
    """Create a test user"""
    
    base_url = "https://localhost:443"
    
    # Disable SSL verification for testing
    session = requests.Session()
    session.verify = False
    
    try:
        # Create a new user
        print("Creating test user...")
        user_data = {
            "username": "testuser",
            "email": "testuser@shtrum.com",
            "full_name": "Test User",
            "password": "testpass123"
        }
        
        # Try API registration
        register_response = session.post(f"{base_url}/auth/register", json=user_data)
        print(f"Registration response status: {register_response.status_code}")
        print(f"Registration response: {register_response.text}")
        
        if register_response.status_code == 200:
            print("User created successfully!")
            return True
        else:
            print(f"Failed to create user: {register_response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Creating test user...")
    success = create_test_user()
    if success:
        print("✅ User creation successful!")
    else:
        print("❌ User creation failed!")
