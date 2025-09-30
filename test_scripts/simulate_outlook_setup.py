#!/usr/bin/env python3
"""
Simulate the exact Outlook account setup process
"""

import requests
import urllib3
import base64
import time
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def simulate_outlook_setup():
    """Simulate the exact steps Outlook takes during account setup"""
    
    print("🔍 Simulating Outlook Account Setup Process")
    print("=" * 60)
    print(f"Simulation started at: {datetime.now().isoformat()}")
    print()
    
    email = "yonatan@shtrum.com"
    domain = "shtrum.com"
    
    # Step 1: Autodiscover JSON
    print("📋 Step 1: Autodiscover JSON Request")
    try:
        json_url = f"https://autodiscover.{domain}/autodiscover/autodiscover.json"
        json_data = {
            "Email": email,
            "Protocol": "Exchange"
        }
        
        response = requests.post(json_url, json=json_data, verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ JSON Autodiscover successful")
            print(f"   Protocol: {data.get('Protocol', 'Unknown')}")
            print(f"   URL: {data.get('Url', 'Unknown')}")
            print(f"   Auth: {data.get('AuthPackage', 'Unknown')}")
        else:
            print(f"   ❌ JSON Autodiscover failed")
            
    except Exception as e:
        print(f"   ❌ JSON Autodiscover error: {e}")
    
    print()
    
    # Step 2: Autodiscover XML
    print("📋 Step 2: Autodiscover XML Request")
    try:
        xml_url = f"https://autodiscover.{domain}/autodiscover/autodiscover.xml"
        xml_data = f'''<?xml version="1.0" encoding="UTF-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>{email}</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>'''
        
        headers = {
            'Content-Type': 'text/xml',
            'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)'
        }
        
        response = requests.post(xml_url, data=xml_data, headers=headers, verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ XML Autodiscover successful")
            print(f"   Response length: {len(response.text)} characters")
            
            # Check for key elements
            if 'EXCH' in response.text:
                print(f"   ✅ Contains EXCH protocol")
            if 'Ntlm' in response.text:
                print(f"   ✅ Contains NTLM authentication")
            if 'mapi' in response.text.lower():
                print(f"   ✅ Contains MAPI settings")
        else:
            print(f"   ❌ XML Autodiscover failed")
            
    except Exception as e:
        print(f"   ❌ XML Autodiscover error: {e}")
    
    print()
    
    # Step 3: MAPI Negotiation
    print("📋 Step 3: MAPI Negotiation")
    try:
        mapi_url = "https://owa.shtrum.com/mapi/emsmdb"
        
        # Step 3a: GET request
        print("   🔍 3a: MAPI GET request")
        response = requests.get(mapi_url, verify=False, timeout=10)
        print(f"      Status: {response.status_code}")
        print(f"      WWW-Authenticate: {response.headers.get('www-authenticate', 'None')}")
        
        # Step 3b: HEAD request
        print("   🔍 3b: MAPI HEAD request")
        response = requests.head(mapi_url, verify=False, timeout=10)
        print(f"      Status: {response.status_code}")
        print(f"      WWW-Authenticate: {response.headers.get('www-authenticate', 'None')}")
        
        # Step 3c: Empty Basic POST
        print("   🔍 3c: Empty Basic POST")
        headers = {
            'Content-Type': 'application/mapi-http',
            'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)'
        }
        response = requests.post(mapi_url, headers=headers, data="", verify=False, timeout=10)
        print(f"      Status: {response.status_code}")
        print(f"      WWW-Authenticate: {response.headers.get('www-authenticate', 'None')}")
        
        # Step 3d: NTLM Type1
        print("   🔍 3d: NTLM Type1 request")
        headers['Authorization'] = 'NTLM TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA='
        response = requests.post(mapi_url, headers=headers, data="", verify=False, timeout=10)
        print(f"      Status: {response.status_code}")
        print(f"      WWW-Authenticate: {response.headers.get('www-authenticate', 'None')}")
        
        if response.status_code == 401 and 'www-authenticate' in response.headers:
            auth_header = response.headers['www-authenticate']
            if 'ntlm' in auth_header.lower():
                print(f"      ✅ NTLM Type2 challenge received")
                
                # Extract Type2 challenge
                if 'TlRMTVNTUAAC' in auth_header:
                    type2_token = auth_header.split('NTLM ')[1]
                    print(f"      Type2 token length: {len(type2_token)}")
                    print(f"      Type2 token preview: {type2_token[:50]}...")
                    
                    # Step 3e: NTLM Type3 (simulated)
                    print("   🔍 3e: NTLM Type3 response (simulated)")
                    print(f"      ✅ Type3 would be sent here in real Outlook")
                    print(f"      ✅ Authentication would complete")
                else:
                    print(f"      ❌ No Type2 challenge in response")
            else:
                print(f"      ❌ No NTLM challenge received")
        else:
            print(f"      ❌ Unexpected response")
            
    except Exception as e:
        print(f"   ❌ MAPI negotiation error: {e}")
    
    print()
    
    # Step 4: EWS Test
    print("📋 Step 4: EWS Connectivity Test")
    try:
        ews_url = "https://owa.shtrum.com/EWS/Exchange.asmx"
        response = requests.get(ews_url, verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 405:
            print(f"   ✅ EWS endpoint accessible (405 = method not allowed, but endpoint exists)")
        else:
            print(f"   Status: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ EWS test error: {e}")
    
    print()
    
    # Summary
    print("📊 Simulation Summary:")
    print("   This simulation shows what Outlook SHOULD be doing")
    print("   If all steps work here, but Outlook still fails:")
    print("   1. Outlook might be using cached settings")
    print("   2. Outlook might be using different endpoints")
    print("   3. There might be network/DNS issues")
    print("   4. Outlook might be failing before reaching the server")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Clear Outlook cache/registry")
    print(f"   2. Check DNS resolution for autodiscover.shtrum.com")
    print(f"   3. Verify SSL certificate is trusted")
    print(f"   4. Try manual server configuration in Outlook")

if __name__ == "__main__":
    simulate_outlook_setup()
