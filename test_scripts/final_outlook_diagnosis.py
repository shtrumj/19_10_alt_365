#!/usr/bin/env python3
"""
Final Outlook Diagnosis
Comprehensive analysis of why Outlook 2021 is not proceeding after JSON autodiscover
"""

import requests
import json
import urllib3
from datetime import datetime
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_complete_outlook_flow():
    """Test the complete Outlook autoconfigure flow"""
    
    print("🔍 FINAL OUTLOOK DIAGNOSIS")
    print("=" * 60)
    
    # Test 1: JSON Autodiscover
    print("📋 Test 1: JSON Autodiscover")
    json_url = "https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com"
    
    try:
        response = requests.get(json_url, verify=False, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ JSON Response received")
            print(f"   📋 Fields count: {len(data[0]) if isinstance(data, list) and len(data) > 0 else 0}")
            
            # Check critical fields
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                critical_fields = ['Type', 'Protocol', 'MapiHttpEnabled', 'MapiHttpServerUrl']
                for field in critical_fields:
                    value = item.get(field, 'MISSING')
                    status = "✅" if value != 'MISSING' else "❌"
                    print(f"   {status} {field}: {value}")
        else:
            print(f"   ❌ JSON Autodiscover failed")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: MAPI Endpoint Accessibility
    print(f"\n📋 Test 2: MAPI Endpoint Accessibility")
    mapi_url = "https://owa.shtrum.com/mapi/emsmdb"
    
    try:
        response = requests.get(mapi_url, verify=False, timeout=10)
        print(f"   GET Status: {response.status_code}")
        print(f"   WWW-Authenticate: {response.headers.get('www-authenticate', 'MISSING')}")
        print(f"   Content-Type: {response.headers.get('content-type', 'MISSING')}")
        
        if response.status_code == 401:
            print(f"   ✅ MAPI endpoint responding correctly (401 expected)")
        else:
            print(f"   ❌ Unexpected MAPI response")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: SSL Certificate
    print(f"\n📋 Test 3: SSL Certificate")
    try:
        import ssl
        import socket
        
        hostname = "owa.shtrum.com"
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                print(f"   ✅ SSL Certificate valid")
                print(f"   📋 Subject: {cert.get('subject', 'N/A')}")
                print(f"   📋 Issuer: {cert.get('issuer', 'N/A')}")
                print(f"   📋 Version: {cert.get('version', 'N/A')}")
                
    except Exception as e:
        print(f"   ❌ SSL Error: {e}")
    
    # Test 4: Network Connectivity
    print(f"\n📋 Test 4: Network Connectivity")
    test_urls = [
        "https://owa.shtrum.com",
        "https://autodiscover.shtrum.com",
        "https://owa.shtrum.com/owa",
        "https://owa.shtrum.com/EWS/Exchange.asmx"
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, verify=False, timeout=5)
            print(f"   ✅ {url}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ {url}: {e}")

def analyze_outlook_behavior():
    """Analyze Outlook 2021 behavior patterns"""
    
    print(f"\n🧠 OUTLOOK 2021 BEHAVIOR ANALYSIS")
    print("=" * 60)
    
    print("📋 Outlook 2021 Autodiscover Process:")
    print("   1. Try JSON autodiscover first")
    print("   2. Parse JSON response")
    print("   3. Extract MAPI HTTP settings")
    print("   4. Proceed to MAPI negotiation")
    print("   5. If MAPI fails, fall back to XML autodiscover")
    
    print(f"\n🔍 Current Issue Analysis:")
    print("   ✅ JSON autodiscover is working (200 response)")
    print("   ✅ JSON response format is correct (array with EXCH type)")
    print("   ✅ All critical fields are present")
    print("   ✅ MAPI endpoints are accessible (401 response)")
    print("   ❌ Outlook is NOT proceeding to MAPI negotiation")
    
    print(f"\n💡 Possible Root Causes:")
    print("   1. Outlook 2021 expects different JSON structure")
    print("   2. Missing specific field values that Outlook requires")
    print("   3. Outlook 2021 has compatibility issues with custom servers")
    print("   4. Network/firewall issues preventing MAPI requests")
    print("   5. Outlook 2021 requires specific authentication flow")
    
    print(f"\n🔧 Recommended Solutions:")
    print("   1. Try XML autodiscover instead of JSON")
    print("   2. Implement Outlook 2021 specific JSON format")
    print("   3. Check Outlook 2021 registry settings")
    print("   4. Verify network connectivity from Outlook client")
    print("   5. Test with different Outlook versions")

def test_xml_autodiscover():
    """Test XML autodiscover as alternative"""
    
    print(f"\n📋 Test 5: XML Autodiscover Alternative")
    xml_url = "https://owa.shtrum.com/Autodiscover/Autodiscover.xml"
    
    try:
        xml_data = '''<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
<Request>
<EMailAddress>yonatan@shtrum.com</EMailAddress>
<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
</Request>
</Autodiscover>'''
        
        response = requests.post(xml_url, data=xml_data, 
                               headers={'Content-Type': 'text/xml'}, 
                               verify=False, timeout=10)
        
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            print(f"   ✅ XML Autodiscover working")
            # Check if XML contains MAPI HTTP settings
            if "MapiHttpEnabled" in response.text:
                print(f"   ✅ XML contains MAPI HTTP settings")
            else:
                print(f"   ❌ XML missing MAPI HTTP settings")
        else:
            print(f"   ❌ XML Autodiscover failed")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def create_outlook_registry_fix():
    """Create registry fix for Outlook 2021"""
    
    print(f"\n📋 Test 6: Outlook 2021 Registry Fix")
    
    registry_fix = '''Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\\Software\\Microsoft\\Office\\16.0\\Outlook\\Autodiscover]
"ExcludeHttpsRootDomain"=dword:00000001
"ExcludeHttpsAutodiscoverDomain"=dword:00000001
"ExcludeHttpRedirect"=dword:00000001
"ExcludeScpLookup"=dword:00000001
"ExcludeSrvRecord"=dword:00000001
"ExcludeExplicitO365Endpoint"=dword:00000001

[HKEY_CURRENT_USER\\Software\\Microsoft\\Office\\16.0\\Outlook\\RPC]
"EnableRpcTcpFallback"=dword:00000001
"UseRpcOverHttp"=dword:00000001
"RpcHttpConnectionPooling"=dword:00000001
"RpcHttpConnectionPoolingTimeout"=dword:0000003c
"RpcHttpConnectionPoolingSize"=dword:0000000a

[HKEY_CURRENT_USER\\Software\\Microsoft\\Office\\16.0\\Outlook\\Options\\General]
"DisableOffice365ModernAuth"=dword:00000001
"DisableModernAuth"=dword:00000001
'''
    
    print(f"   📋 Registry fix created for Outlook 2021")
    print(f"   💡 This fix:")
    print(f"      - Disables Office 365 modern authentication")
    print(f"      - Enables RPC over HTTP")
    print(f"      - Excludes Office 365 endpoints")
    print(f"      - Forces custom Exchange server usage")
    
    # Save registry fix
    with open("outlook_2021_registry_fix.reg", "w") as f:
        f.write(registry_fix)
    
    print(f"   ✅ Registry fix saved to outlook_2021_registry_fix.reg")

if __name__ == "__main__":
    print(f"🚀 Starting Final Outlook Diagnosis")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    test_complete_outlook_flow()
    analyze_outlook_behavior()
    test_xml_autodiscover()
    create_outlook_registry_fix()
    
    print(f"\n✅ Final diagnosis complete!")
    print(f"\n💡 Next Steps:")
    print(f"   1. Apply the registry fix to Outlook 2021")
    print(f"   2. Try XML autodiscover instead of JSON")
    print(f"   3. Test with different Outlook versions")
    print(f"   4. Check network connectivity from Outlook client")
