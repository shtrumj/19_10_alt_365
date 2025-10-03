#!/usr/bin/env python3
"""
NTLM Authentication Flow Test

This script tests the NTLM authentication flow that Outlook uses
to identify and fix authentication issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import requests
import base64
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://owa.shtrum.com"
MAPI_URL = f"{BASE_URL}/mapi/emsmdb"

def test_ntlm_flow():
    """Test the complete NTLM authentication flow"""
    print("🔐 TESTING NTLM AUTHENTICATION FLOW")
    print("=" * 50)
    
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)'
    })
    
    # Step 1: Initial request (should get 401 with NTLM challenge)
    print("Step 1: Sending initial request (expect 401 NTLM challenge)")
    response = session.post(MAPI_URL, data=b'')
    
    print(f"  Status: {response.status_code}")
    print(f"  WWW-Authenticate: {response.headers.get('WWW-Authenticate', 'Not present')}")
    
    if response.status_code != 401 or 'NTLM' not in response.headers.get('WWW-Authenticate', ''):
        print("  ❌ FAIL: Expected 401 with NTLM challenge")
        return False
    
    print("  ✅ PASS: NTLM challenge received")
    
    # Step 2: Send NTLM Type 1 message
    print("\nStep 2: Sending NTLM Type 1 message")
    
    # Create NTLM Type 1 message
    ntlm_type1 = base64.b64encode(
        b'NTLMSSP\x00'  # Signature
        b'\x01\x00\x00\x00'  # Type 1
        b'\x07\x82\x08\x00'  # Flags
        + b'\x00' * 16  # Domain and workstation (empty)
    ).decode('ascii')
    
    headers = {'Authorization': f'NTLM {ntlm_type1}'}
    response = session.post(MAPI_URL, data=b'', headers=headers)
    
    print(f"  Status: {response.status_code}")
    print(f"  WWW-Authenticate: {response.headers.get('WWW-Authenticate', 'Not present')}")
    print(f"  Content-Length: {response.headers.get('Content-Length', 'Not present')}")
    
    # Check if we get a Type 2 response
    if response.status_code == 401 and 'NTLM' in response.headers.get('WWW-Authenticate', ''):
        auth_header = response.headers.get('WWW-Authenticate', '')
        if auth_header.startswith('NTLM ') and len(auth_header) > 10:
            print("  ✅ PASS: NTLM Type 2 challenge received")
            type2_successful = True
        else:
            print("  ⚠️  WARNING: NTLM header present but may not be Type 2")
            type2_successful = False
    else:
        print("  ❌ FAIL: Expected 401 with NTLM Type 2 challenge")
        type2_successful = False
    
    # Step 3: Send NTLM Type 3 message (simplified - would normally contain credentials)
    print("\nStep 3: Sending NTLM Type 3 message")
    
    # Create a simplified NTLM Type 3 message
    ntlm_type3 = base64.b64encode(
        b'NTLMSSP\x00'  # Signature
        b'\x03\x00\x00\x00'  # Type 3
        + b'\x00' * 48  # Simplified response (real would have encrypted credentials)
    ).decode('ascii')
    
    headers = {'Authorization': f'NTLM {ntlm_type3}'}
    response = session.post(MAPI_URL, data=b'', headers=headers)
    
    print(f"  Status: {response.status_code}")
    print(f"  Content-Type: {response.headers.get('Content-Type', 'Not present')}")
    
    if response.status_code == 200:
        print("  ✅ PASS: NTLM Type 3 accepted")
        type3_successful = True
    else:
        print(f"  ⚠️  WARNING: NTLM Type 3 returned {response.status_code}")
        type3_successful = False
    
    # Step 4: Test actual MAPI Connect with Basic auth (fallback)
    print("\nStep 4: Testing MAPI Connect with Basic authentication")
    
    # Create MAPI Connect request
    user_dn = "/o=First Organization/ou=Exchange Administrative Group/cn=Recipients/cn=yonatan"
    connect_data = b''
    connect_data += (0).to_bytes(4, 'little')  # Request type
    connect_data += (0).to_bytes(4, 'little')  # Flags
    connect_data += len(user_dn.encode()).to_bytes(4, 'little')  # DN length
    connect_data += user_dn.encode('utf-8')  # DN
    
    basic_auth = base64.b64encode(b"yonatan@shtrum.com:Gib$0n579!").decode('ascii')
    headers = {
        'Authorization': f'Basic {basic_auth}',
        'Content-Type': 'application/mapi-http'
    }
    
    response = session.post(MAPI_URL, data=connect_data, headers=headers)
    
    print(f"  Status: {response.status_code}")
    print(f"  Content-Type: {response.headers.get('Content-Type', 'Not present')}")
    print(f"  X-SessionCookie: {response.headers.get('X-SessionCookie', 'Not present')}")
    
    if response.status_code == 200 and response.headers.get('X-SessionCookie'):
        print("  ✅ PASS: MAPI Connect successful with Basic auth")
        connect_successful = True
    else:
        print("  ❌ FAIL: MAPI Connect failed")
        connect_successful = False
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 NTLM FLOW TEST SUMMARY")
    print("=" * 50)
    
    results = {
        "Initial Challenge": "✅ PASS",
        "NTLM Type 1": "✅ PASS" if type2_successful else "❌ FAIL",
        "NTLM Type 2": "✅ PASS" if type2_successful else "❌ FAIL", 
        "NTLM Type 3": "✅ PASS" if type3_successful else "❌ FAIL",
        "MAPI Connect": "✅ PASS" if connect_successful else "❌ FAIL"
    }
    
    for step, result in results.items():
        print(f"  {step}: {result}")
    
    all_passed = all("✅" in result for result in results.values())
    
    if all_passed:
        print("\n🎉 All NTLM flow tests passed!")
        print("The authentication flow is working correctly.")
    else:
        print("\n⚠️  Some NTLM flow tests failed.")
        print("This may explain why Outlook is getting stuck.")
    
    return all_passed

def main():
    """Run NTLM flow test"""
    success = test_ntlm_flow()
    
    if not success:
        print("\n🔧 TROUBLESHOOTING RECOMMENDATIONS:")
        print("1. Check that NTLM Type 2 challenges are properly formatted")
        print("2. Verify MAPI/HTTP protocol compatibility")
        print("3. Ensure authentication headers are correctly processed")
        print("4. Check for SSL/TLS certificate trust issues")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
