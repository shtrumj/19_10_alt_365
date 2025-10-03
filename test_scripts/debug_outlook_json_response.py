#!/usr/bin/env python3
"""
Debug Outlook JSON Autodiscover Response Issues
Analyze what's preventing Outlook from proceeding after JSON response
"""

import requests
import json
import urllib3
from datetime import datetime
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_json_autodiscover_response():
    """Test the current JSON autodiscover response and analyze it"""
    
    print("🔍 DEBUGGING OUTLOOK JSON AUTODISCOVER RESPONSE")
    print("=" * 60)
    
    # Test the current JSON autodiscover response
    url = "https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com"
    
    try:
        print(f"📡 Testing JSON autodiscover: {url}")
        response = requests.get(url, verify=False, timeout=10)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers:")
        for key, value in response.headers.items():
            print(f"   {key}: {value}")
        
        if response.status_code == 200:
            try:
                json_data = response.json()
                print(f"\n📋 JSON Response Analysis:")
                print(f"   Type: {type(json_data)}")
                print(f"   Length: {len(json_data) if isinstance(json_data, list) else 'N/A'}")
                
                if isinstance(json_data, list) and len(json_data) > 0:
                    first_item = json_data[0]
                    print(f"\n📋 First Item Keys: {list(first_item.keys())}")
                    
                    # Check for critical fields
                    critical_fields = [
                        "Type", "Protocol", "Url", "AuthPackage", "MapiHttpEnabled", 
                        "MapiHttpVersion", "MapiHttpServerUrl", "ExternalHostname", 
                        "InternalHostname", "EwsUrl", "EcpUrl"
                    ]
                    
                    print(f"\n🔍 Critical Fields Check:")
                    for field in critical_fields:
                        value = first_item.get(field, "MISSING")
                        status = "✅" if value != "MISSING" else "❌"
                        print(f"   {status} {field}: {value}")
                    
                    # Check MAPI HTTP settings specifically
                    mapi_fields = ["MapiHttpEnabled", "MapiHttpVersion", "MapiHttpServerUrl"]
                    print(f"\n🔍 MAPI HTTP Settings:")
                    for field in mapi_fields:
                        value = first_item.get(field, "MISSING")
                        status = "✅" if value != "MISSING" else "❌"
                        print(f"   {status} {field}: {value}")
                    
                    # Check if response format matches expected structure
                    print(f"\n🔍 Response Format Analysis:")
                    print(f"   Is Array: {isinstance(json_data, list)}")
                    print(f"   Array Length: {len(json_data) if isinstance(json_data, list) else 'N/A'}")
                    
                    if isinstance(json_data, list) and len(json_data) > 0:
                        item = json_data[0]
                        print(f"   Has Type Field: {'Type' in item}")
                        print(f"   Has Protocol Field: {'Protocol' in item}")
                        print(f"   Type Value: {item.get('Type', 'MISSING')}")
                        print(f"   Protocol Value: {item.get('Protocol', 'MISSING')}")
                        
                        # Check if it's the right format for Outlook 2021
                        if item.get('Type') == 'EXCH' and item.get('Protocol') == 'Exchange':
                            print("   ✅ Format appears correct for Outlook 2021")
                        else:
                            print("   ❌ Format may not be correct for Outlook 2021")
                    
                    # Full JSON response for analysis
                    print(f"\n📋 Full JSON Response:")
                    print(json.dumps(json_data, indent=2))
                    
                else:
                    print("❌ JSON response is not a list or is empty")
                    print(f"Raw response: {response.text}")
                    
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON: {e}")
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing JSON autodiscover: {e}")

def test_alternative_json_formats():
    """Test different JSON autodiscover response formats"""
    
    print(f"\n🧪 TESTING ALTERNATIVE JSON FORMATS")
    print("=" * 60)
    
    # Test different URL formats that Outlook might try
    test_urls = [
        "https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com",
        "https://autodiscover.shtrum.com/autodiscover/autodiscover.json",
        "https://autodiscover.shtrum.com/autodiscover/autodiscover.json?EmailAddress=yonatan@shtrum.com",
        "https://owa.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com",
        "https://owa.shtrum.com/autodiscover/autodiscover.json"
    ]
    
    for url in test_urls:
        try:
            print(f"\n📡 Testing: {url}")
            response = requests.get(url, verify=False, timeout=5)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    print(f"   ✅ Valid JSON response")
                    if isinstance(json_data, list) and len(json_data) > 0:
                        print(f"   📋 First item keys: {list(json_data[0].keys())}")
                except:
                    print(f"   ❌ Invalid JSON")
            else:
                print(f"   ❌ Failed")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def check_mapi_endpoints():
    """Check if MAPI endpoints are accessible"""
    
    print(f"\n🔍 CHECKING MAPI ENDPOINTS")
    print("=" * 60)
    
    mapi_urls = [
        "https://owa.shtrum.com/mapi/emsmdb",
        "https://owa.shtrum.com/mapi/nspi"
    ]
    
    for url in mapi_urls:
        try:
            print(f"\n📡 Testing: {url}")
            
            # Test GET request
            response = requests.get(url, verify=False, timeout=5)
            print(f"   GET Status: {response.status_code}")
            print(f"   GET Headers: {dict(response.headers)}")
            
            # Test HEAD request
            response = requests.head(url, verify=False, timeout=5)
            print(f"   HEAD Status: {response.status_code}")
            print(f"   HEAD Headers: {dict(response.headers)}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

def analyze_outlook_behavior():
    """Analyze what Outlook might be expecting"""
    
    print(f"\n🧠 OUTLOOK BEHAVIOR ANALYSIS")
    print("=" * 60)
    
    print("📋 Outlook 2021 Autodiscover Process:")
    print("   1. Try JSON autodiscover first")
    print("   2. If successful, proceed to MAPI negotiation")
    print("   3. If MAPI fails, fall back to XML autodiscover")
    print("   4. If XML fails, show manual configuration")
    
    print(f"\n🔍 Potential Issues:")
    print("   1. JSON response format not compatible with Outlook 2021")
    print("   2. Missing critical fields in JSON response")
    print("   3. MAPI endpoints not accessible or not responding correctly")
    print("   4. Authentication issues in MAPI negotiation")
    print("   5. SSL/TLS certificate issues")
    print("   6. Network connectivity issues")
    
    print(f"\n💡 Debugging Steps:")
    print("   1. Check JSON response format")
    print("   2. Verify all critical fields are present")
    print("   3. Test MAPI endpoint accessibility")
    print("   4. Check SSL certificate validity")
    print("   5. Monitor network traffic during Outlook setup")

if __name__ == "__main__":
    print(f"🚀 Starting Outlook JSON Autodiscover Debug")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    test_json_autodiscover_response()
    test_alternative_json_formats()
    check_mapi_endpoints()
    analyze_outlook_behavior()
    
    print(f"\n✅ Debug analysis complete!")
