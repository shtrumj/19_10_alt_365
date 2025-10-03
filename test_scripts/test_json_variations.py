#!/usr/bin/env python3
"""
Test Different JSON Autodiscover Response Formats
Try various formats that might work better with Outlook 2021
"""

import requests
import json
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_current_response():
    """Test the current JSON response format"""
    
    print("🔍 TESTING CURRENT JSON RESPONSE FORMAT")
    print("=" * 60)
    
    url = "https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com"
    
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Current format works (Status: {response.status_code})")
            print(f"📋 Response type: {type(data)}")
            print(f"📋 Response length: {len(data) if isinstance(data, list) else 'N/A'}")
            
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                print(f"📋 Key fields present:")
                for key in ['Type', 'Protocol', 'MapiHttpEnabled', 'MapiHttpServerUrl']:
                    value = item.get(key, 'MISSING')
                    status = "✅" if value != 'MISSING' else "❌"
                    print(f"   {status} {key}: {value}")
        else:
            print(f"❌ Current format failed (Status: {response.status_code})")
            
    except Exception as e:
        print(f"❌ Error testing current format: {e}")

def suggest_improvements():
    """Suggest potential improvements to the JSON response"""
    
    print(f"\n💡 SUGGESTED IMPROVEMENTS")
    print("=" * 60)
    
    print("🔍 Based on Microsoft documentation, try these improvements:")
    
    print(f"\n1. Add missing fields that Outlook 2021 might expect:")
    print("   - ServerDN (Server Distinguished Name)")
    print("   - ServerVersion (Exchange version)")
    print("   - LoginName (in domain\\username format)")
    print("   - RpcUrl (RPC over HTTP URL)")
    print("   - OABUrl (Offline Address Book URL)")
    
    print(f"\n2. Ensure proper field ordering:")
    print("   - Type should be first")
    print("   - Protocol should be second")
    print("   - Critical MAPI fields should be early")
    
    print(f"\n3. Check field values:")
    print("   - Type: 'EXCH' (not 'Exchange')")
    print("   - Protocol: 'Exchange'")
    print("   - MapiHttpEnabled: true (not 'True')")
    print("   - MapiHttpVersion: 2 (not '2.0')")
    
    print(f"\n4. Add Outlook 2021 specific fields:")
    print("   - AccountType: 'Exchange'")
    print("   - Action: 'settings'")
    print("   - Connect: 'On'")
    print("   - DomainRequired: false")
    print("   - SPA: false")
    print("   - AuthRequired: true")

def test_alternative_endpoints():
    """Test alternative autodiscover endpoints"""
    
    print(f"\n🧪 TESTING ALTERNATIVE ENDPOINTS")
    print("=" * 60)
    
    # Test different endpoint patterns
    test_cases = [
        {
            "name": "Current JSON endpoint",
            "url": "https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com",
            "expected": "Should work"
        },
        {
            "name": "Alternative JSON endpoint",
            "url": "https://owa.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com",
            "expected": "Should work"
        },
        {
            "name": "XML autodiscover",
            "url": "https://owa.shtrum.com/Autodiscover/Autodiscover.xml",
            "expected": "Should work with POST"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📡 Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Expected: {test_case['expected']}")
        
        try:
            if "xml" in test_case['name'].lower():
                # Test XML with POST
                xml_data = '''<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
<Request>
<EMailAddress>yonatan@shtrum.com</EMailAddress>
<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
</Request>
</Autodiscover>'''
                response = requests.post(test_case['url'], data=xml_data, 
                                       headers={'Content-Type': 'text/xml'}, 
                                       verify=False, timeout=10)
            else:
                # Test JSON with GET
                response = requests.get(test_case['url'], verify=False, timeout=10)
            
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            if response.status_code == 200:
                print(f"   ✅ Success")
                if 'json' in response.headers.get('Content-Type', ''):
                    try:
                        data = response.json()
                        print(f"   📋 JSON response received")
                        if isinstance(data, list) and len(data) > 0:
                            print(f"   📋 First item keys: {list(data[0].keys())}")
                    except:
                        print(f"   📋 Non-JSON response")
                else:
                    print(f"   📋 XML response received")
            else:
                print(f"   ❌ Failed")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def check_outlook_requirements():
    """Check what Outlook 2021 specifically requires"""
    
    print(f"\n📋 OUTLOOK 2021 REQUIREMENTS CHECK")
    print("=" * 60)
    
    print("🔍 Outlook 2021 JSON Autodiscover Requirements:")
    print("   1. Response must be a JSON array")
    print("   2. First item must have Type: 'EXCH'")
    print("   3. Must include MapiHttpEnabled: true")
    print("   4. Must include MapiHttpServerUrl")
    print("   5. Must include proper authentication settings")
    print("   6. Must include EWS and OAB URLs")
    
    print(f"\n🔍 Critical Fields for Outlook 2021:")
    critical_fields = [
        "Type", "Protocol", "Url", "AuthPackage", "MapiHttpEnabled",
        "MapiHttpVersion", "MapiHttpServerUrl", "ExternalHostname",
        "InternalHostname", "EwsUrl", "EcpUrl", "OABUrl"
    ]
    
    for field in critical_fields:
        print(f"   ✅ {field} - Required")
    
    print(f"\n🔍 Optional but Recommended Fields:")
    optional_fields = [
        "ServerDN", "ServerVersion", "LoginName", "RpcUrl",
        "PublicFolderServer", "ASUrl", "EwsPartnerUrl"
    ]
    
    for field in optional_fields:
        print(f"   💡 {field} - Recommended")

if __name__ == "__main__":
    print(f"🚀 Starting JSON Response Format Testing")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    test_current_response()
    suggest_improvements()
    test_alternative_endpoints()
    check_outlook_requirements()
    
    print(f"\n✅ Testing complete!")
