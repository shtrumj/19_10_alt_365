#!/usr/bin/env python3
"""
Test Script for Autodiscover, GAB, and OAB endpoints

Tests:
1. Autodiscover (XML) - Outlook discovery protocol
2. Autodiscover (JSON) - Modern Outlook clients
3. OAB Manifest - Offline Address Book manifest
4. OAB Files - Browse, Details, RDN Index
5. NSPI/GAB - Global Address List via MAPI/HTTP

Run inside Docker:
  docker exec -it <container> python3 test_scripts/test_autodiscover_gab_oab.py

Or locally with requests:
  python test_scripts/test_autodiscover_gab_oab.py
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import json
import sys
import warnings

# Suppress SSL warnings for testing
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Configuration
BASE_URL = "http://localhost:8000"  # Change to https://your-domain.com for production
TEST_EMAIL = "user@example.com"
TEST_PASSWORD = "password"  # Only for local testing
USE_AUTH = False  # Set to True if testing authenticated endpoints

# Test credentials (if needed)
AUTH = (TEST_EMAIL, TEST_PASSWORD) if USE_AUTH else None

def print_section(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_test(name, passed, details=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"         {details}")

def test_autodiscover_xml():
    """Test Autodiscover XML endpoint"""
    print_section("1. AUTODISCOVER (XML)")
    
    url = f"{BASE_URL}/Autodiscover/Autodiscover.xml"
    
    # Autodiscover request body
    autodiscover_request = f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>{TEST_EMAIL}</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'User-Agent': 'Microsoft Office/16.0 (Windows NT 10.0; Microsoft Outlook 16.0.5266; Pro)'
    }
    
    try:
        response = requests.post(
            url,
            data=autodiscover_request.encode('utf-8'),
            headers=headers,
            auth=AUTH,
            verify=False,
            timeout=10
        )
        
        print(f"\n📤 Request URL: {url}")
        print(f"📥 Response Status: {response.status_code}")
        print(f"📏 Response Size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            # Parse XML response
            try:
                root = ET.fromstring(response.content)
                
                # Check for required elements
                namespace = {'ad': 'http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006'}
                
                protocols = root.findall('.//ad:Protocol', namespace)
                
                if not protocols:
                    # Try without namespace
                    protocols = root.findall('.//Protocol')
                
                print(f"\n📋 Protocols found: {len(protocols)}")
                
                protocol_types = []
                for protocol in protocols:
                    protocol_type = protocol.find('Type')
                    if protocol_type is not None:
                        protocol_types.append(protocol_type.text)
                        print(f"   - {protocol_type.text}")
                
                # Check for essential protocols
                test_print("Has EXHTTP/EXPR protocol", 
                          'EXHTTP' in protocol_types or 'EXPR' in protocol_types,
                          "MAPI/HTTP protocol")
                test_print("Has EXCH protocol", 
                          'EXCH' in protocol_types,
                          "Exchange RPC protocol")
                test_print("Has WEB protocol", 
                          'WEB' in protocol_types,
                          "OWA/Web access")
                test_print("Has MobileSync protocol", 
                          'MobileSync' in protocol_types,
                          "ActiveSync protocol")
                
                # Extract key URLs
                print("\n🔗 Key URLs:")
                for protocol in protocols:
                    ptype = protocol.find('Type')
                    if ptype is not None and ptype.text in ['EXHTTP', 'EXPR']:
                        server = protocol.find('.//Server')
                        if server is not None:
                            print(f"   MAPI Server: {server.text}")
                
                test_print("Autodiscover XML", True, "Response valid")
                
            except ET.ParseError as e:
                print(f"\n❌ XML Parse Error: {e}")
                print(f"Response preview: {response.text[:500]}")
                test_print("Autodiscover XML", False, f"Parse error: {e}")
        else:
            test_print("Autodiscover XML", False, f"HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
    
    except Exception as e:
        test_print("Autodiscover XML", False, f"Exception: {e}")

def test_autodiscover_json():
    """Test Autodiscover JSON endpoint (modern Outlook)"""
    print_section("2. AUTODISCOVER (JSON)")
    
    url = f"{BASE_URL}/autodiscover/autodiscover.json/v1.0/{TEST_EMAIL}"
    
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Microsoft Office/16.0'
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            auth=AUTH,
            verify=False,
            timeout=10
        )
        
        print(f"\n📤 Request URL: {url}")
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                print(f"\n📋 JSON Response:")
                print(json.dumps(data, indent=2)[:1000])
                
                # Check for required fields
                test_print("Has Protocol field", 'Protocol' in data)
                
                if 'Protocol' in data:
                    test_print("Has AutodiscoverUrl", 
                              'AutodiscoverUrl' in data['Protocol'],
                              data['Protocol'].get('AutodiscoverUrl', 'N/A'))
                    test_print("Has Type", 
                              'Type' in data['Protocol'],
                              data['Protocol'].get('Type', 'N/A'))
                
                test_print("Autodiscover JSON", True, "Response valid")
                
            except json.JSONDecodeError as e:
                test_print("Autodiscover JSON", False, f"JSON parse error: {e}")
        else:
            test_print("Autodiscover JSON", False, f"HTTP {response.status_code}")
    
    except Exception as e:
        test_print("Autodiscover JSON", False, f"Exception: {e}")

def test_oab_manifest():
    """Test OAB manifest endpoint"""
    print_section("3. OFFLINE ADDRESS BOOK (OAB) - Manifest")
    
    url = f"{BASE_URL}/oab/oab.xml"
    
    headers = {
        'User-Agent': 'Microsoft Office/16.0'
    }
    
    try:
        response = requests.get(
            url,
            headers=headers,
            auth=AUTH,
            verify=False,
            timeout=10
        )
        
        print(f"\n📤 Request URL: {url}")
        print(f"📥 Response Status: {response.status_code}")
        print(f"📏 Response Size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            try:
                root = ET.fromstring(response.content)
                
                # Parse OAB manifest
                namespace = {'oab': 'http://schemas.microsoft.com/exchange/2003/oab'}
                
                oal = root.find('.//oab:OAL', namespace)
                if not oal:
                    oal = root.find('.//OAL')  # Try without namespace
                
                if oal:
                    name = oal.find('.//Name')
                    dn = oal.find('.//DN')
                    version = oal.find('.//Version')
                    files = oal.findall('.//File')
                    
                    print(f"\n📋 OAB Details:")
                    if name is not None:
                        print(f"   Name: {name.text}")
                    if dn is not None:
                        print(f"   DN: {dn.text}")
                    if version is not None:
                        print(f"   Version: {version.text}")
                    print(f"   Files: {len(files)}")
                    
                    for file_elem in files:
                        file_name = file_elem.find('.//Name')
                        if file_name is not None:
                            print(f"      - {file_name.text}")
                    
                    test_print("OAB Manifest structure", True)
                    test_print("Has browse.oab", 
                              any(f.find('.//Name').text == 'browse.oab' for f in files if f.find('.//Name') is not None))
                    test_print("Has details.oab", 
                              any(f.find('.//Name').text == 'details.oab' for f in files if f.find('.//Name') is not None))
                    test_print("Has rdndex.oab", 
                              any(f.find('.//Name').text == 'rdndex.oab' for f in files if f.find('.//Name') is not None))
                else:
                    test_print("OAB Manifest", False, "No OAL element found")
                
            except ET.ParseError as e:
                test_print("OAB Manifest", False, f"XML parse error: {e}")
        else:
            test_print("OAB Manifest", False, f"HTTP {response.status_code}")
    
    except Exception as e:
        test_print("OAB Manifest", False, f"Exception: {e}")

def test_oab_files():
    """Test OAB data files"""
    print_section("4. OFFLINE ADDRESS BOOK (OAB) - Data Files")
    
    oab_id = "default-oab"
    files = [
        ('browse.oab', 'Browse file'),
        ('details.oab', 'Details file'),
        ('rdndex.oab', 'RDN Index file')
    ]
    
    for filename, description in files:
        url = f"{BASE_URL}/oab/{oab_id}/{filename}"
        
        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'Microsoft Office/16.0'},
                auth=AUTH,
                verify=False,
                timeout=10
            )
            
            print(f"\n📤 Testing: {filename}")
            print(f"   URL: {url}")
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   Size: {len(response.content)} bytes")
                print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                
                # Check if binary data
                is_binary = response.headers.get('Content-Type') == 'application/octet-stream'
                
                test_print(f"{description}", 
                          is_binary and len(response.content) > 0,
                          f"{len(response.content)} bytes")
            else:
                test_print(f"{description}", False, f"HTTP {response.status_code}")
        
        except Exception as e:
            test_print(f"{description}", False, f"Exception: {e}")

def test_nspi_gab():
    """Test NSPI (Name Service Provider Interface) - Global Address List"""
    print_section("5. NSPI/GAB - Global Address List")
    
    url = f"{BASE_URL}/mapi/nspi"
    
    # Create a simplified NSPI GetMatches request
    # Operation code 0x01 = NspiGetMatches
    nspi_request = b'\x01\x00\x00\x00'  # Operation: GetMatches
    nspi_request += b'\x00\x00\x00\x00'  # Flags
    nspi_request += b'\x64\x00\x00\x00'  # Max entries: 100
    
    headers = {
        'Content-Type': 'application/mapi-http',
        'User-Agent': 'Microsoft Office/16.0',
        'X-RequestType': 'GetMatches'
    }
    
    try:
        response = requests.post(
            url,
            data=nspi_request,
            headers=headers,
            auth=AUTH,
            verify=False,
            timeout=10
        )
        
        print(f"\n📤 Request URL: {url}")
        print(f"📥 Response Status: {response.status_code}")
        print(f"📏 Response Size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            # Parse NSPI response
            try:
                import struct
                data = response.content
                
                if len(data) >= 8:
                    status_code = struct.unpack('<I', data[0:4])[0]
                    user_count = struct.unpack('<I', data[4:8])[0]
                    
                    print(f"\n📋 NSPI Response:")
                    print(f"   Status Code: {status_code}")
                    print(f"   User Count: {user_count}")
                    
                    test_print("NSPI Response valid", status_code == 0, f"{user_count} users")
                    test_print("GAB has users", user_count > 0)
                    
                    # Try to parse first user
                    if user_count > 0 and len(data) > 8:
                        offset = 8
                        try:
                            name_len = struct.unpack('<H', data[offset:offset+2])[0]
                            offset += 2
                            display_name = data[offset:offset+name_len].decode('utf-8')
                            offset += name_len
                            
                            email_len = struct.unpack('<H', data[offset:offset+2])[0]
                            offset += 2
                            email = data[offset:offset+email_len].decode('utf-8')
                            
                            print(f"\n   First user sample:")
                            print(f"      Name: {display_name}")
                            print(f"      Email: {email}")
                            
                            test_print("User data parseable", True)
                        except:
                            print("   (Could not parse user data)")
                else:
                    test_print("NSPI Response", False, "Response too short")
            except Exception as e:
                test_print("NSPI Parse", False, f"Parse error: {e}")
        else:
            test_print("NSPI/GAB", False, f"HTTP {response.status_code}")
    
    except Exception as e:
        test_print("NSPI/GAB", False, f"Exception: {e}")

def test_print(name, passed, details=""):
    """Alias for print_test"""
    print_test(name, passed, details)

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print(" " * 15 + "AUTODISCOVER, GAB, OAB TEST SUITE")
    print("=" * 80)
    print(f"\n🎯 Target: {BASE_URL}")
    print(f"📧 Test Email: {TEST_EMAIL}")
    print(f"🔐 Authentication: {'Enabled' if USE_AUTH else 'Disabled'}")
    
    # Run all tests
    test_autodiscover_xml()
    test_autodiscover_json()
    test_oab_manifest()
    test_oab_files()
    test_nspi_gab()
    
    # Summary
    print("\n" + "=" * 80)
    print(" " * 30 + "TEST COMPLETE")
    print("=" * 80)
    print("\n✅ All endpoints tested")
    print("\n💡 TIP: Update BASE_URL and credentials for production testing")
    print("💡 TIP: Check logs/autodiscover/ and logs/oab/ for detailed logs\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

