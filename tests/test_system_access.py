#!/usr/bin/env python3
"""
Test system access and check logs
"""
import requests
import time
import json

def test_system():
    """Test the system and check logs"""
    print("🧪 Testing system access...")
    
    # Test the main OWA interface
    try:
        print("📡 Testing OWA interface...")
        response = requests.get("https://owa.shtrum.com/", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ OWA interface accessible")
        else:
            print("   ❌ OWA interface not accessible")
    except Exception as e:
        print(f"   ❌ OWA interface error: {e}")
    
    # Test the debug endpoint
    try:
        print("🔍 Testing debug endpoint...")
        response = requests.get("https://owa.shtrum.com/debug/test-parsing", verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Debug endpoint working: {data.get('success', False)}")
            print(f"   Parsed content: '{data.get('parsed_content', '')}'")
        else:
            print(f"   ❌ Debug endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Debug endpoint error: {e}")
    
    print("\n📁 Checking logs...")
    # This would require Docker access to check logs
    print("   (Logs can be checked with: docker exec 365-email-system ls -la logs/)")

if __name__ == "__main__":
    test_system()
