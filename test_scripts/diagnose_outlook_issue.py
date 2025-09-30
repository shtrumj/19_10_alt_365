#!/usr/bin/env python3
"""
Comprehensive diagnosis of Outlook connectivity issues
"""

import requests
import urllib3
import socket
import ssl
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_dns_resolution():
    """Test DNS resolution for critical domains"""
    
    print("🔍 Testing DNS Resolution")
    print("=" * 40)
    
    domains = [
        "autodiscover.shtrum.com",
        "owa.shtrum.com", 
        "shtrum.com"
    ]
    
    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"✅ {domain}: {ip}")
        except Exception as e:
            print(f"❌ {domain}: {e}")

def test_ssl_certificate():
    """Test SSL certificate validity"""
    
    print(f"\n🔍 Testing SSL Certificates")
    print("=" * 40)
    
    hosts = [
        "autodiscover.shtrum.com:443",
        "owa.shtrum.com:443"
    ]
    
    for host in hosts:
        try:
            hostname, port = host.split(':')
            port = int(port)
            
            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    subject = dict(x[0] for x in cert['subject'])
                    issuer = dict(x[0] for x in cert['issuer'])
                    
                    print(f"✅ {hostname}:")
                    print(f"   Subject: {subject.get('commonName', 'Unknown')}")
                    print(f"   Issuer: {issuer.get('organizationName', 'Unknown')}")
                    print(f"   Valid: {cert['notAfter']}")
                    
        except Exception as e:
            print(f"❌ {hostname}: {e}")

def test_network_connectivity():
    """Test basic network connectivity"""
    
    print(f"\n🔍 Testing Network Connectivity")
    print("=" * 40)
    
    hosts = [
        ("autodiscover.shtrum.com", 443),
        ("owa.shtrum.com", 443),
        ("shtrum.com", 443)
    ]
    
    for hostname, port in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result == 0:
                print(f"✅ {hostname}:{port} - Connected")
            else:
                print(f"❌ {hostname}:{port} - Connection failed")
                
        except Exception as e:
            print(f"❌ {hostname}:{port} - {e}")

def test_outlook_specific_endpoints():
    """Test endpoints that Outlook specifically uses"""
    
    print(f"\n🔍 Testing Outlook-Specific Endpoints")
    print("=" * 40)
    
    # Test autodiscover with different methods
    autodiscover_tests = [
        ("https://autodiscover.shtrum.com/autodiscover/autodiscover.xml", "GET"),
        ("https://autodiscover.shtrum.com/autodiscover/autodiscover.xml", "POST"),
        ("https://autodiscover.shtrum.com/autodiscover/autodiscover.json", "GET"),
        ("https://autodiscover.shtrum.com/autodiscover/autodiscover.json", "POST"),
    ]
    
    for url, method in autodiscover_tests:
        try:
            if method == "GET":
                response = requests.get(url, verify=False, timeout=10)
            else:
                response = requests.post(url, verify=False, timeout=10)
            
            print(f"✅ {method} {url}: {response.status_code}")
            
        except Exception as e:
            print(f"❌ {method} {url}: {e}")
    
    # Test MAPI endpoints
    mapi_tests = [
        ("https://owa.shtrum.com/mapi/emsmdb", "GET"),
        ("https://owa.shtrum.com/mapi/emsmdb", "HEAD"),
        ("https://owa.shtrum.com/mapi/emsmdb", "POST"),
    ]
    
    for url, method in mapi_tests:
        try:
            if method == "GET":
                response = requests.get(url, verify=False, timeout=10)
            elif method == "HEAD":
                response = requests.head(url, verify=False, timeout=10)
            else:
                response = requests.post(url, verify=False, timeout=10)
            
            print(f"✅ {method} {url}: {response.status_code}")
            
            # Check for NTLM challenge
            if response.status_code == 401 and 'www-authenticate' in response.headers:
                auth_header = response.headers['www-authenticate']
                if 'ntlm' in auth_header.lower():
                    print(f"   🔐 NTLM challenge present")
                if 'negotiate' in auth_header.lower():
                    print(f"   🔐 Negotiate challenge present")
            
        except Exception as e:
            print(f"❌ {method} {url}: {e}")

def test_outlook_user_agent():
    """Test with Outlook user agent"""
    
    print(f"\n🔍 Testing with Outlook User Agent")
    print("=" * 40)
    
    outlook_ua = "Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)"
    
    # Test autodiscover with Outlook UA
    try:
        url = "https://autodiscover.shtrum.com/autodiscover/autodiscover.xml"
        headers = {'User-Agent': outlook_ua}
        
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        print(f"✅ Autodiscover with Outlook UA: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   📋 Response length: {len(response.text)}")
            if 'Exchange' in response.text:
                print(f"   ✅ Contains Exchange settings")
            if 'Ntlm' in response.text:
                print(f"   ✅ Contains NTLM authentication")
                
    except Exception as e:
        print(f"❌ Autodiscover with Outlook UA: {e}")
    
    # Test MAPI with Outlook UA
    try:
        url = "https://owa.shtrum.com/mapi/emsmdb"
        headers = {
            'User-Agent': outlook_ua,
            'Content-Type': 'application/mapi-http'
        }
        
        response = requests.post(url, headers=headers, data="", verify=False, timeout=10)
        print(f"✅ MAPI with Outlook UA: {response.status_code}")
        
        if response.status_code == 401 and 'www-authenticate' in response.headers:
            auth_header = response.headers['www-authenticate']
            print(f"   🔐 Auth header: {auth_header}")
            
    except Exception as e:
        print(f"❌ MAPI with Outlook UA: {e}")

def main():
    """Main diagnostic function"""
    
    print("🔍 Comprehensive Outlook Connectivity Diagnosis")
    print("=" * 60)
    print(f"Diagnosis started at: {datetime.now().isoformat()}")
    print()
    
    # Test DNS resolution
    test_dns_resolution()
    
    # Test SSL certificates
    test_ssl_certificate()
    
    # Test network connectivity
    test_network_connectivity()
    
    # Test Outlook-specific endpoints
    test_outlook_specific_endpoints()
    
    # Test with Outlook user agent
    test_outlook_user_agent()
    
    print(f"\n📊 Diagnosis Summary:")
    print(f"   This comprehensive test checks all aspects of Outlook connectivity")
    print(f"   If all tests pass, but Outlook still fails:")
    print(f"   1. Outlook might be using cached settings")
    print(f"   2. Outlook might be configured manually")
    print(f"   3. Outlook might be using different credentials")
    print(f"   4. Outlook might be failing at the authentication step")
    
    print(f"\n💡 Troubleshooting Steps:")
    print(f"   1. Clear Outlook cache and registry")
    print(f"   2. Try manual server configuration")
    print(f"   3. Check Outlook error logs")
    print(f"   4. Verify user credentials")
    print(f"   5. Try different Outlook version")

if __name__ == "__main__":
    main()
