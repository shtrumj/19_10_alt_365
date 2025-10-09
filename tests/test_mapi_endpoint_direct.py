#!/usr/bin/env python3
"""
Test MAPI endpoint directly to see if it's working when Outlook tries to connect
"""

import requests
import base64
import struct
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_mapi_endpoint_direct():
    """Test MAPI endpoint with Outlook-like requests"""
    
    print("🔍 TESTING MAPI ENDPOINT DIRECTLY")
    print("=" * 50)
    
    # Test 1: GET request (Outlook probe)
    print("\n1. Testing GET request (Outlook probe)...")
    try:
        response = requests.get(
            "https://owa.shtrum.com/mapi/emsmdb",
            headers={
                "User-Agent": "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)",
                "Accept": "*/*",
                "Connection": "Keep-Alive"
            },
            verify=False,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        if response.status_code == 401:
            print("   ✅ GET request returns 401 (expected)")
        else:
            print(f"   ❌ GET request returned {response.status_code} (unexpected)")
    except Exception as e:
        print(f"   ❌ GET request failed: {e}")
    
    # Test 2: HEAD request (Outlook probe)
    print("\n2. Testing HEAD request (Outlook probe)...")
    try:
        response = requests.head(
            "https://owa.shtrum.com/mapi/emsmdb",
            headers={
                "User-Agent": "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)",
                "Accept": "*/*",
                "Connection": "Keep-Alive"
            },
            verify=False,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        if response.status_code == 401:
            print("   ✅ HEAD request returns 401 (expected)")
        else:
            print(f"   ❌ HEAD request returned {response.status_code} (unexpected)")
    except Exception as e:
        print(f"   ❌ HEAD request failed: {e}")
    
    # Test 3: POST request with NTLM Type1 (Outlook authentication)
    print("\n3. Testing POST request with NTLM Type1...")
    try:
        # Generate NTLM Type1 message
        ntlm_type1 = generate_ntlm_type1()
        
        response = requests.post(
            "https://owa.shtrum.com/mapi/emsmdb",
            headers={
                "User-Agent": "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)",
                "Content-Type": "application/mapi-http",
                "Authorization": f"NTLM {ntlm_type1}",
                "Connection": "Keep-Alive"
            },
            data=b"",
            verify=False,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        if response.status_code == 401:
            print("   ✅ POST request returns 401 (expected)")
            if "WWW-Authenticate" in response.headers:
                print(f"   ✅ WWW-Authenticate header: {response.headers['WWW-Authenticate']}")
            else:
                print("   ❌ Missing WWW-Authenticate header")
        else:
            print(f"   ❌ POST request returned {response.status_code} (unexpected)")
    except Exception as e:
        print(f"   ❌ POST request failed: {e}")
    
    # Test 4: Test with different User-Agent (simulate different Outlook versions)
    print("\n4. Testing with different User-Agent...")
    user_agents = [
        "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)",
        "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro) MAPI/1.0",
        "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro) MAPI/2.0",
        "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro) MAPI/3.0"
    ]
    
    for ua in user_agents:
        try:
            response = requests.get(
                "https://owa.shtrum.com/mapi/emsmdb",
                headers={
                    "User-Agent": ua,
                    "Accept": "*/*",
                    "Connection": "Keep-Alive"
                },
                verify=False,
                timeout=5
            )
            print(f"   {ua[:50]}... -> {response.status_code}")
        except Exception as e:
            print(f"   {ua[:50]}... -> Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ MAPI endpoint testing complete!")

def generate_ntlm_type1():
    """Generate NTLM Type1 message"""
    # NTLM Type1 message structure
    signature = b"NTLMSSP\x00"
    message_type = struct.pack("<I", 1)  # Type 1
    flags = struct.pack("<I", 0x00000001 | 0x00000002 | 0x00000004)  # NTLMSSP_NEGOTIATE_UNICODE | NTLMSSP_NEGOTIATE_OEM | NTLMSSP_REQUEST_TARGET
    
    # Domain and workstation (empty for Type1)
    domain_len = struct.pack("<H", 0)
    domain_max_len = struct.pack("<H", 0)
    domain_offset = struct.pack("<I", 0)
    
    workstation_len = struct.pack("<H", 0)
    workstation_max_len = struct.pack("<H", 0)
    workstation_offset = struct.pack("<I", 0)
    
    # Version (optional)
    version = b"\x05\x01\x28\x0a\x00\x00\x00\x0f"
    
    type1 = signature + message_type + flags + domain_len + domain_max_len + domain_offset + workstation_len + workstation_max_len + workstation_offset + version
    
    return base64.b64encode(type1).decode('ascii')

if __name__ == "__main__":
    test_mapi_endpoint_direct()
