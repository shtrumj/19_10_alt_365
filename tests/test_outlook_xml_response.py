#!/usr/bin/env python3
"""
Test Outlook XML Autodiscover Response
Analyze the XML response structure for Outlook 2021 compatibility
"""

import requests
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_xml_autodiscover_response():
    """Test and analyze the XML autodiscover response"""
    
    print("🔍 TESTING OUTLOOK XML AUTODISCOVER RESPONSE")
    print("=" * 60)
    
    # Test XML autodiscover
    url = "https://owa.shtrum.com/Autodiscover/Autodiscover.xml"
    
    xml_data = '''<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
<Request>
<EMailAddress>yonatan@shtrum.com</EMailAddress>
<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
</Request>
</Autodiscover>'''
    
    try:
        response = requests.post(url, data=xml_data, 
                               headers={'Content-Type': 'text/xml'}, 
                               verify=False, timeout=10)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Content-Type: {response.headers.get('Content-Type')}")
        print(f"📊 Content-Length: {len(response.text)}")
        
        if response.status_code == 200:
            # Parse XML response
            try:
                root = ET.fromstring(response.text)
                
                # Check for critical elements
                print(f"\n📋 XML Response Analysis:")
                
                # Check ErrorCode
                error_code = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}ErrorCode')
                if error_code is not None:
                    print(f"   ✅ ErrorCode: {error_code.text}")
                else:
                    print(f"   ❌ ErrorCode: MISSING")
                
                # Check Protocol Type
                protocol_type = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}Type')
                if protocol_type is not None:
                    print(f"   ✅ Protocol Type: {protocol_type.text}")
                else:
                    print(f"   ❌ Protocol Type: MISSING")
                
                # Check MAPI HTTP settings
                mapi_http_enabled = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}MapiHttpEnabled')
                if mapi_http_enabled is not None:
                    print(f"   ✅ MapiHttpEnabled: {mapi_http_enabled.text}")
                else:
                    print(f"   ❌ MapiHttpEnabled: MISSING")
                
                mapi_http_server_url = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}MapiHttpServerUrl')
                if mapi_http_server_url is not None:
                    print(f"   ✅ MapiHttpServerUrl: {mapi_http_server_url.text}")
                else:
                    print(f"   ❌ MapiHttpServerUrl: MISSING")
                
                # Check Internal/External URLs
                internal_url = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}Internal/{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}Url')
                if internal_url is not None:
                    print(f"   ✅ Internal URL: {internal_url.text}")
                else:
                    print(f"   ❌ Internal URL: MISSING")
                
                external_url = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}External/{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}Url')
                if external_url is not None:
                    print(f"   ✅ External URL: {external_url.text}")
                else:
                    print(f"   ❌ External URL: MISSING")
                
                # Check for critical Outlook 2021 requirements
                print(f"\n🔍 Outlook 2021 Critical Requirements:")
                
                # Check if MAPI HTTP is properly configured
                if (mapi_http_enabled is not None and mapi_http_enabled.text.lower() == 'true' and
                    mapi_http_server_url is not None and 'emsmdb' in mapi_http_server_url.text):
                    print(f"   ✅ MAPI HTTP properly configured")
                else:
                    print(f"   ❌ MAPI HTTP not properly configured")
                
                # Check if Internal/External URLs are set
                if (internal_url is not None and 'emsmdb' in internal_url.text and
                    external_url is not None and 'emsmdb' in external_url.text):
                    print(f"   ✅ Internal/External URLs properly configured")
                else:
                    print(f"   ❌ Internal/External URLs not properly configured")
                
                # Check authentication settings
                auth_package = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}AuthPackage')
                if auth_package is not None:
                    print(f"   ✅ AuthPackage: {auth_package.text}")
                else:
                    print(f"   ❌ AuthPackage: MISSING")
                
                # Check SSL settings
                ssl = root.find('.//{http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006}SSL')
                if ssl is not None:
                    print(f"   ✅ SSL: {ssl.text}")
                else:
                    print(f"   ❌ SSL: MISSING")
                
                # Full XML response for analysis
                print(f"\n📋 Full XML Response (first 1000 chars):")
                print(response.text[:1000] + "..." if len(response.text) > 1000 else response.text)
                
            except ET.ParseError as e:
                print(f"   ❌ XML Parse Error: {e}")
                print(f"   Raw response: {response.text[:500]}")
        else:
            print(f"   ❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error testing XML autodiscover: {e}")

def analyze_outlook_requirements():
    """Analyze what Outlook 2021 specifically requires"""
    
    print(f"\n🧠 OUTLOOK 2021 XML REQUIREMENTS ANALYSIS")
    print("=" * 60)
    
    print("📋 Outlook 2021 XML Autodiscover Requirements:")
    print("   1. ErrorCode must be 'NoError'")
    print("   2. Protocol Type must be 'EXCH'")
    print("   3. MapiHttpEnabled must be 'true'")
    print("   4. MapiHttpServerUrl must point to emsmdb endpoint")
    print("   5. Internal/External URLs must be properly configured")
    print("   6. AuthPackage must be 'Ntlm' or 'Negotiate'")
    print("   7. SSL must be 'On'")
    print("   8. Server must be accessible")
    print("   9. Port must be 443")
    
    print(f"\n🔍 Common Issues:")
    print("   1. Missing MapiHttpEnabled element")
    print("   2. Incorrect MapiHttpServerUrl format")
    print("   3. Missing Internal/External URL elements")
    print("   4. Wrong authentication method")
    print("   5. SSL not properly configured")
    print("   6. Server not accessible from Outlook client")
    
    print(f"\n💡 Debugging Steps:")
    print("   1. Verify XML response structure")
    print("   2. Check MAPI HTTP configuration")
    print("   3. Test MAPI endpoint accessibility")
    print("   4. Verify authentication settings")
    print("   5. Check network connectivity")

if __name__ == "__main__":
    print(f"🚀 Starting Outlook XML Response Analysis")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    test_xml_autodiscover_response()
    analyze_outlook_requirements()
    
    print(f"\n✅ Analysis complete!")
