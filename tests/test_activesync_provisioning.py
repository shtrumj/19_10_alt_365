#!/usr/bin/env python3
"""
Test script to verify ActiveSync provisioning enforcement.
This tests that unprovisioned devices receive HTTP 449 responses.
"""

import requests
import base64
import json
from datetime import datetime

# Configuration
BASE_URL = "https://owa.shtrum.com"
USERNAME = "yonatan"
PASSWORD = "Gib$0n579!"
import time
DEVICE_ID = f"test-device-provisioning-{int(time.time())}"

def test_provisioning_enforcement():
    """Test that unprovisioned devices are forced to provision first."""
    print("🔐 Testing ActiveSync Provisioning Enforcement")
    print("=" * 60)
    
    # Create basic auth header
    auth_string = f"{USERNAME}:{PASSWORD}"
    auth_bytes = auth_string.encode('ascii')
    auth_header = base64.b64encode(auth_bytes).decode('ascii')
    headers = {
        'Authorization': f'Basic {auth_header}',
        'User-Agent': 'Test-Client/1.0',
        'MS-ASProtocolVersion': '16.0',
        'Content-Type': 'application/vnd.ms-sync.wbxml'
    }
    
    # Test 1: OPTIONS should work (not require provisioning)
    print("\n1. Testing OPTIONS (should work without provisioning)...")
    try:
        response = requests.options(f"{BASE_URL}/Microsoft-Server-ActiveSync", headers=headers, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ OPTIONS works without provisioning (correct)")
        else:
            print("   ❌ OPTIONS failed unexpectedly")
    except Exception as e:
        print(f"   ❌ OPTIONS failed: {e}")
    
    # Test 2: FolderSync should return HTTP 449 (require provisioning)
    print("\n2. Testing FolderSync without provisioning (should return HTTP 449)...")
    try:
        params = {
            'Cmd': 'FolderSync',
            'DeviceId': DEVICE_ID,
            'DeviceType': 'SmartPhone',
            'SyncKey': '0'
        }
        response = requests.post(f"{BASE_URL}/Microsoft-Server-ActiveSync", 
                               headers=headers, params=params, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 449:
            print("   ✅ FolderSync correctly returns HTTP 449 (provisioning required)")
        else:
            print(f"   ❌ FolderSync returned {response.status_code} instead of 449")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ FolderSync failed: {e}")
    
    # Test 3: Sync should return HTTP 449 (require provisioning)
    print("\n3. Testing Sync without provisioning (should return HTTP 449)...")
    try:
        params = {
            'Cmd': 'Sync',
            'DeviceId': DEVICE_ID,
            'DeviceType': 'SmartPhone',
            'SyncKey': '0',
            'CollectionId': '1'
        }
        response = requests.post(f"{BASE_URL}/Microsoft-Server-ActiveSync", 
                               headers=headers, params=params, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 449:
            print("   ✅ Sync correctly returns HTTP 449 (provisioning required)")
        else:
            print(f"   ❌ Sync returned {response.status_code} instead of 449")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Sync failed: {e}")
    
    # Test 4: Provision should work and return success
    print("\n4. Testing Provision command...")
    try:
        params = {
            'Cmd': 'Provision',
            'DeviceId': DEVICE_ID,
            'DeviceType': 'SmartPhone'
        }
        response = requests.post(f"{BASE_URL}/Microsoft-Server-ActiveSync", 
                               headers=headers, params=params, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Provision command succeeded")
            print(f"   Response: {response.text[:200]}...")
        else:
            print(f"   ❌ Provision returned {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Provision failed: {e}")
    
    # Test 5: After provisioning, FolderSync should work
    print("\n5. Testing FolderSync after provisioning...")
    try:
        params = {
            'Cmd': 'FolderSync',
            'DeviceId': DEVICE_ID,
            'DeviceType': 'SmartPhone',
            'SyncKey': '0'
        }
        response = requests.post(f"{BASE_URL}/Microsoft-Server-ActiveSync", 
                               headers=headers, params=params, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ FolderSync works after provisioning")
            print(f"   Response: {response.text[:200]}...")
        else:
            print(f"   ❌ FolderSync still failed after provisioning: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ FolderSync after provisioning failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Provisioning enforcement test completed!")

if __name__ == "__main__":
    test_provisioning_enforcement()
