#!/usr/bin/env python3
"""
Test the live system to verify email parsing is working
"""
import requests
import json

def test_live_system():
    """Test the live system endpoints"""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing live system...")
    
    # Test the debug endpoint
    try:
        print("📡 Testing debug endpoint...")
        response = requests.get(f"{base_url}/debug/test-parsing")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Debug test successful: {data['success']}")
            print(f"   Parsed content: '{data['parsed_content']}'")
        else:
            print(f"❌ Debug test failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Debug test error: {e}")
    
    # Test the logs endpoint
    try:
        print("📁 Testing logs endpoint...")
        response = requests.get(f"{base_url}/debug/logs")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Logs endpoint working: {len(data['log_files'])} log files")
        else:
            print(f"❌ Logs endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Logs endpoint error: {e}")

if __name__ == "__main__":
    test_live_system()
