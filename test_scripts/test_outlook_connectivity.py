#!/usr/bin/env python3
"""
Test Outlook connectivity and endpoints
"""

import requests
import urllib3
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_outlook_connectivity():
    """Test all endpoints that Outlook might use"""
    
    print("🔍 Testing Outlook Connectivity")
    print("=" * 60)
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    base_url = "https://owa.shtrum.com"
    autodiscover_url = "https://autodiscover.shtrum.com"
    
    endpoints = [
        # Autodiscover endpoints
        (f"{autodiscover_url}/autodiscover/autodiscover.xml", "Autodiscover XML"),
        (f"{autodiscover_url}/autodiscover/autodiscover.json", "Autodiscover JSON"),
        (f"{autodiscover_url}/autodiscover/autodiscover.xml", "Autodiscover XML (POST)"),
        
        # MAPI endpoints
        (f"{base_url}/mapi/emsmdb", "MAPI EMSMDB"),
        (f"{base_url}/mapi/emsmdb", "MAPI EMSMDB (GET)"),
        (f"{base_url}/mapi/emsmdb", "MAPI EMSMDB (HEAD)"),
        
        # EWS endpoints
        (f"{base_url}/EWS/Exchange.asmx", "EWS Exchange.asmx"),
        (f"{base_url}/EWS/Exchange.asmx", "EWS Exchange.asmx (GET)"),
        
        # OWA endpoints
        (f"{base_url}/owa", "OWA"),
        (f"{base_url}/owa/", "OWA Root"),
        
        # RPC endpoints
        (f"{base_url}/rpc/rpcproxy.dll", "RPC Proxy"),
        
        # OAB endpoints
        (f"{base_url}/oab/oab.xml", "OAB XML"),
    ]
    
    results = []
    
    for url, description in endpoints:
        print(f"🔍 Testing {description}...")
        
        try:
            # Test GET request
            response = requests.get(url, verify=False, timeout=10)
            status = response.status_code
            headers = dict(response.headers)
            
            print(f"   ✅ {description}: {status}")
            
            # Check for important headers
            important_headers = ['www-authenticate', 'content-type', 'server']
            for header in important_headers:
                if header in headers:
                    print(f"      {header}: {headers[header]}")
            
            results.append({
                'endpoint': description,
                'url': url,
                'status': status,
                'success': True,
                'headers': headers
            })
            
        except requests.exceptions.Timeout:
            print(f"   ⏰ {description}: Timeout")
            results.append({
                'endpoint': description,
                'url': url,
                'status': 'Timeout',
                'success': False
            })
        except requests.exceptions.ConnectionError:
            print(f"   ❌ {description}: Connection Error")
            results.append({
                'endpoint': description,
                'url': url,
                'status': 'Connection Error',
                'success': False
            })
        except Exception as e:
            print(f"   ❌ {description}: {str(e)}")
            results.append({
                'endpoint': description,
                'url': url,
                'status': str(e),
                'success': False
            })
    
    print(f"\n📊 Connectivity Summary:")
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    
    if failed:
        print(f"\n❌ Failed Endpoints:")
        for result in failed:
            print(f"   - {result['endpoint']}: {result['status']}")
    
    # Test autodiscover specifically
    print(f"\n🔍 Testing Autodiscover with Outlook-style request...")
    
    try:
        autodiscover_data = '''<?xml version="1.0" encoding="UTF-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>yonatan@shtrum.com</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>'''
        
        headers = {
            'Content-Type': 'text/xml',
            'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)'
        }
        
        response = requests.post(
            f"{autodiscover_url}/autodiscover/autodiscover.xml",
            data=autodiscover_data,
            headers=headers,
            verify=False,
            timeout=10
        )
        
        print(f"   ✅ Autodiscover XML: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   📋 Response contains Exchange settings: {'Exchange' in response.text}")
            print(f"   📋 Response contains MAPI settings: {'mapi' in response.text.lower()}")
            print(f"   📋 Response contains NTLM settings: {'ntlm' in response.text.lower()}")
        
    except Exception as e:
        print(f"   ❌ Autodiscover test failed: {e}")
    
    # Test MAPI with Outlook-style request
    print(f"\n🔍 Testing MAPI with Outlook-style request...")
    
    try:
        headers = {
            'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)',
            'Content-Type': 'application/mapi-http',
            'Authorization': 'NTLM TlRMTVNTUAABAAAAB4IIAAAAAAAAAAAAAAAAAAAAAAA='
        }
        
        response = requests.post(
            f"{base_url}/mapi/emsmdb",
            headers=headers,
            data="",
            verify=False,
            timeout=10
        )
        
        print(f"   ✅ MAPI with Outlook UA: {response.status_code}")
        
        if 'www-authenticate' in response.headers:
            auth_header = response.headers['www-authenticate']
            print(f"   🔐 WWW-Authenticate: {auth_header}")
            
            if 'ntlm' in auth_header.lower():
                print(f"   ✅ NTLM challenge received")
            if 'negotiate' in auth_header.lower():
                print(f"   ✅ Negotiate challenge received")
        
    except Exception as e:
        print(f"   ❌ MAPI test failed: {e}")
    
    print(f"\n💡 Recommendations:")
    print(f"   1. All endpoints should return 200 or 401 (for auth)")
    print(f"   2. MAPI should return 401 with WWW-Authenticate header")
    print(f"   3. Autodiscover should return 200 with Exchange settings")
    print(f"   4. If any endpoints fail, Outlook won't be able to connect")
    
    return results

if __name__ == "__main__":
    test_outlook_connectivity()
