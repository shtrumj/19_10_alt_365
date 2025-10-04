#!/usr/bin/env python3
"""
Create SRV record for autodiscover using Cloudflare API
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
DOMAIN = 'shtrum.com'
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

def create_srv_record(zone_id):
    """Create SRV record for autodiscover"""
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "type": "SRV",
        "name": f"_autodiscover._tcp.{DOMAIN}",
        "content": f"0 1 443 {HOSTNAME}",
        "ttl": 300,
        "priority": 0,
        "weight": 1,
        "port": 443,
        "target": HOSTNAME
    }
    
    url = DNS_RECORDS_URL.format(zone_id=zone_id)
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            print(f"✅ Created SRV record: _autodiscover._tcp.{DOMAIN} → {HOSTNAME}:443")
            return True
        else:
            print(f"❌ Error creating SRV record: {result['errors']}")
            return False
    else:
        print(f"❌ HTTP error creating SRV record: {response.status_code} - {response.text}")
        return False

def main():
    """Main function"""
    print("🚀 Creating SRV record for autodiscover")
    print("=" * 40)
    
    # Get zone ID
    zone_id = get_zone_id()
    if not zone_id:
        return
    
    # Create SRV record
    success = create_srv_record(zone_id)
    
    if success:
        print("\n✅ SRV record created successfully!")
        print(f"   _autodiscover._tcp.{DOMAIN} → {HOSTNAME}:443")
        print("\n🔍 Test with:")
        print(f"   nslookup -type=SRV _autodiscover._tcp.{DOMAIN}")
    else:
        print("\n❌ Failed to create SRV record")

if __name__ == "__main__":
    main()
