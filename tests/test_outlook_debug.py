#!/usr/bin/env python3
"""
Debug Outlook autoconfigure issues by testing various scenarios
"""

import requests
import base64
import struct
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_outlook_scenarios():
    """Test various scenarios that might affect Outlook autoconfigure"""
    
    print("=== Outlook Autoconfigure Debug ===")
    
    # Test 1: Check autodiscover response
    print("\n1. Testing Autodiscover...")
    try:
        autodiscover_url = "https://autodiscover.shtrum.com/autodiscover/autodiscover.xml"
        autodiscover_data = '''<?xml version="1.0" encoding="UTF-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>yonatan@shtrum.com</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>'''
        
        response = requests.post(autodiscover_url, 
                              data=autodiscover_data,
                              headers={'Content-Type': 'text/xml'},
                              verify=False)
        print(f"Autodiscover Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Autodiscover working")
        else:
            print("❌ Autodiscover failed")
    except Exception as e:
        print(f"❌ Autodiscover error: {e}")
    
    # Test 2: Check MAPI endpoint accessibility
    print("\n2. Testing MAPI Endpoint...")
    try:
        mapi_url = "https://owa.shtrum.com/mapi/emsmdb"
        response = requests.get(mapi_url, verify=False)
        print(f"MAPI GET Status: {response.status_code}")
        print(f"WWW-Authenticate: {response.headers.get('WWW-Authenticate', 'None')}")
        
        if "Negotiate, NTLM" in response.headers.get('WWW-Authenticate', ''):
            print("✅ MAPI supports both Negotiate and NTLM")
        else:
            print("❌ MAPI authentication methods issue")
    except Exception as e:
        print(f"❌ MAPI error: {e}")
    
    # Test 3: Test NTLM Type1 -> Type2 flow
    print("\n3. Testing NTLM Type1 -> Type2...")
    try:
        session = requests.Session()
        type1_token = "TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA="
        headers = {
            "Authorization": f"NTLM {type1_token}",
            "Content-Type": "application/mapi-http"
        }
        
        response = session.post(mapi_url, headers=headers, data="", verify=False)
        print(f"NTLM Type1->Type2 Status: {response.status_code}")
        
        auth_header = response.headers.get('WWW-Authenticate', '')
        if auth_header.startswith('NTLM '):
            type2_token = auth_header.split(' ', 1)[1]
            print(f"Type2 token length: {len(type2_token)}")
            
            # Decode and analyze Type2
            try:
                type2_raw = base64.b64decode(type2_token)
                print(f"Type2 raw length: {len(type2_raw)}")
                
                # Check NTLM signature
                if type2_raw.startswith(b"NTLMSSP\x00"):
                    print("✅ Type2 has correct NTLM signature")
                else:
                    print("❌ Type2 missing NTLM signature")
                
                # Check message type
                if len(type2_raw) >= 12:
                    msg_type = struct.unpack('<I', type2_raw[8:12])[0]
                    print(f"Type2 message type: {msg_type}")
                    if msg_type == 2:
                        print("✅ Type2 has correct message type")
                    else:
                        print("❌ Type2 wrong message type")
                
                # Check flags
                if len(type2_raw) >= 20:
                    flags = struct.unpack('<I', type2_raw[20:24])[0]
                    print(f"Type2 flags: 0x{flags:08x}")
                    
                    # Check for important flags
                    important_flags = {
                        0x00000001: "UNICODE",
                        0x00000200: "SIGN", 
                        0x00080000: "NTLM2_KEY",
                        0x00010000: "TargetTypeServer",
                        0x00020000: "NTLM",
                        0x00004000: "Target Info"
                    }
                    
                    for flag, name in important_flags.items():
                        if flags & flag:
                            print(f"  ✅ {name} flag set")
                        else:
                            print(f"  ❌ {name} flag missing")
                
            except Exception as e:
                print(f"❌ Type2 analysis error: {e}")
        else:
            print("❌ No NTLM challenge received")
            
    except Exception as e:
        print(f"❌ NTLM Type1->Type2 error: {e}")
    
    # Test 4: Test with different User-Agent (simulate Outlook)
    print("\n4. Testing with Outlook User-Agent...")
    try:
        outlook_headers = {
            "User-Agent": "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)",
            "Authorization": f"NTLM {type1_token}",
            "Content-Type": "application/mapi-http"
        }
        
        response = session.post(mapi_url, headers=outlook_headers, data="", verify=False)
        print(f"Outlook UA Status: {response.status_code}")
        print(f"Outlook UA WWW-Authenticate: {response.headers.get('WWW-Authenticate', 'None')}")
        
    except Exception as e:
        print(f"❌ Outlook UA test error: {e}")
    
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    test_outlook_scenarios()
