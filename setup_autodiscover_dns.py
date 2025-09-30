#!/usr/bin/env python3
"""
Setup Autodiscover DNS Records using Cloudflare API
Based on Microsoft Autodiscover specification:
https://learn.microsoft.com/en-us/previous-versions/office/developer/exchange-server-interoperability-guidance/hh352638(v=exchg.140)
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cloudflare API configuration
CLOUDFLARE_API_KEY = os.getenv('CLOUDFLARE_API_KEY')
CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
DOMAIN = 'shtrum.com'  # Use the root domain
HOSTNAME = os.getenv('HOSTNAME', 'owa.shtrum.com')

# Cloudflare API endpoints
BASE_URL = "https://api.cloudflare.com/client/v4"
ZONE_URL = f"{BASE_URL}/zones"
DNS_RECORDS_URL = f"{BASE_URL}/zones/{{zone_id}}/dns_records"

def get_zone_id():
    """Get the zone ID for the domain"""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {"name": DOMAIN}
    response = requests.get(ZONE_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data["success"] and data["result"]:
            zone_id = data["result"][0]["id"]
            print(f"✅ Found zone ID for {DOMAIN}: {zone_id}")
            return zone_id
        else:
            print(f"❌ No zone found for {DOMAIN}")
            return None
    else:
        print(f"❌ Error getting zone ID: {response.status_code} - {response.text}")
        return None

def get_server_ip():
    """Get the server IP address"""
    import socket
    try:
        ip = socket.gethostbyname(HOSTNAME)
        print(f"✅ Server IP for {HOSTNAME}: {ip}")
        return ip
    except socket.gaierror:
        print(f"❌ Could not resolve {HOSTNAME}")
        return None

def create_dns_record(zone_id, record_type, name, content, ttl=300, priority=None, weight=None, port=None, target=None):
    """Create a DNS record"""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl
    }
    
    if priority is not None:
        data["priority"] = priority
    if weight is not None:
        data["weight"] = weight
    if port is not None:
        data["port"] = port
    if target is not None:
        data["target"] = target
    
    url = DNS_RECORDS_URL.format(zone_id=zone_id)
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            print(f"✅ Created {record_type} record: {name} → {content}")
            return True
        else:
            print(f"❌ Error creating {record_type} record: {result['errors']}")
            return False
    else:
        print(f"❌ HTTP error creating {record_type} record: {response.status_code} - {response.text}")
        return False

def check_existing_record(zone_id, record_type, name):
    """Check if a DNS record already exists"""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    url = DNS_RECORDS_URL.format(zone_id=zone_id)
    params = {"type": record_type, "name": name}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data["success"] and data["result"]:
            return data["result"][0]
    return None

def main():
    """Main function to set up autodiscover DNS records"""
    print("🚀 Setting up Autodiscover DNS Records")
    print("=" * 50)
    
    # Validate configuration
    if not CLOUDFLARE_API_KEY:
        print("❌ CLOUDFLARE_API_KEY not found in .env file")
        return
    
    if not CLOUDFLARE_EMAIL:
        print("❌ CLOUDFLARE_EMAIL not found in .env file")
        return
    
    print(f"📧 Cloudflare Email: {CLOUDFLARE_EMAIL}")
    print(f"🌐 Domain: {DOMAIN}")
    print(f"🖥️  Hostname: {HOSTNAME}")
    print()
    
    # Get zone ID
    zone_id = get_zone_id()
    if not zone_id:
        return
    
    # Get server IP
    server_ip = get_server_ip()
    if not server_ip:
        return
    
    print()
    print("📋 Creating DNS Records:")
    print("-" * 30)
    
    # 1. Create A record for autodiscover.shtrum.com
    autodiscover_name = f"autodiscover.{DOMAIN}"
    existing_a = check_existing_record(zone_id, "A", autodiscover_name)
    if existing_a:
        print(f"ℹ️  A record already exists: {autodiscover_name} → {existing_a['content']}")
    else:
        create_dns_record(zone_id, "A", autodiscover_name, server_ip)
    
    # 2. Create SRV record for _autodiscover._tcp.shtrum.com
    srv_name = f"_autodiscover._tcp.{DOMAIN}"
    existing_srv = check_existing_record(zone_id, "SRV", srv_name)
    if existing_srv:
        print(f"ℹ️  SRV record already exists: {srv_name} → {existing_srv['content']}")
    else:
        # SRV record format: priority weight port target
        create_dns_record(zone_id, "SRV", srv_name, f"0 1 443 {HOSTNAME}", priority=0, weight=1, port=443, target=HOSTNAME)
    
    print()
    print("✅ Autodiscover DNS setup complete!")
    print()
    print("📋 Created Records:")
    print(f"   A: autodiscover.{DOMAIN} → {server_ip}")
    print(f"   SRV: _autodiscover._tcp.{DOMAIN} → 0 1 443 {HOSTNAME}")
    print()
    print("🔍 Testing DNS Resolution:")
    print(f"   nslookup autodiscover.{DOMAIN}")
    print(f"   nslookup -type=SRV _autodiscover._tcp.{DOMAIN}")

if __name__ == "__main__":
    main()
