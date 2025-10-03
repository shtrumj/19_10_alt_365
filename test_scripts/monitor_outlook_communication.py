#!/usr/bin/env python3
"""
Monitor and analyze Outlook communication with the server
"""

import requests
import json
import time
import urllib3
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def monitor_outlook_communication():
    """Monitor real-time communication between Outlook and server"""
    
    print("🔍 Starting Outlook Communication Monitor")
    print("=" * 60)
    
    base_url = "https://owa.shtrum.com"
    debug_url = f"{base_url}/debug"
    
    # Test the debug endpoints
    try:
        print("📊 Testing debug endpoints...")
        
        # Get communication logs
        response = requests.get(f"{debug_url}/communication", verify=False)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Communication logs: {data.get('total_logs', 0)} entries")
        else:
            print(f"❌ Failed to get communication logs: {response.status_code}")
        
        # Get Outlook-specific requests
        response = requests.get(f"{debug_url}/outlook-requests", verify=False)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Outlook requests: {data.get('outlook_requests', 0)} entries")
            
            if data.get('logs'):
                print("\n📋 Recent Outlook requests:")
                for log in data['logs'][-5:]:
                    timestamp = log.get('timestamp', 'Unknown')
                    user_agent = log.get('user_agent', 'Unknown')
                    path = log.get('path', 'Unknown')
                    method = log.get('method', 'Unknown')
                    print(f"  {timestamp} | {method} {path} | {user_agent}")
        else:
            print(f"❌ Failed to get Outlook requests: {response.status_code}")
        
        # Get authentication flow
        response = requests.get(f"{debug_url}/authentication-flow", verify=False)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Auth requests: {data.get('auth_requests', 0)} entries")
        else:
            print(f"❌ Failed to get auth flow: {response.status_code}")
        
        # Get NTLM analysis
        response = requests.get(f"{debug_url}/ntlm-analysis", verify=False)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ NTLM requests: {data.get('total_ntlm_requests', 0)}")
            print(f"   Type1: {data.get('type1_requests', 0)}")
            print(f"   Type3: {data.get('type3_requests', 0)}")
            
            if data.get('type3_logs'):
                print("   ✅ Type3 authentication successful!")
            else:
                print("   ❌ No Type3 authentication found")
        else:
            print(f"❌ Failed to get NTLM analysis: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error accessing debug endpoints: {e}")
    
    print("\n" + "=" * 60)
    print("🔍 Monitoring for new Outlook connections...")
    print("   Try setting up Outlook account now and watch for activity")
    print("   Press Ctrl+C to stop monitoring")
    
    # Monitor for new activity
    try:
        last_log_count = 0
        while True:
            time.sleep(5)
            
            try:
                response = requests.get(f"{debug_url}/communication", verify=False)
                if response.status_code == 200:
                    data = response.json()
                    current_count = data.get('total_logs', 0)
                    
                    if current_count > last_log_count:
                        new_logs = current_count - last_log_count
                        print(f"🆕 {new_logs} new requests detected!")
                        
                        # Get the latest logs
                        if data.get('logs'):
                            latest_log = data['logs'][-1]
                            timestamp = latest_log.get('timestamp', 'Unknown')
                            user_agent = latest_log.get('user_agent', 'Unknown')
                            path = latest_log.get('path', 'Unknown')
                            method = latest_log.get('method', 'Unknown')
                            is_outlook = latest_log.get('is_outlook', False)
                            
                            print(f"   📍 {timestamp} | {method} {path}")
                            print(f"   🖥️  {user_agent}")
                            print(f"   🔍 Outlook detected: {is_outlook}")
                            
                            if is_outlook:
                                print("   🎯 OUTLOOK CLIENT DETECTED!")
                                
                                # Check for authentication
                                auth_header = latest_log.get('authorization', '')
                                if auth_header:
                                    print(f"   🔐 Auth header: {auth_header[:50]}...")
                                    if 'ntlm' in auth_header.lower():
                                        print("   🔐 NTLM authentication detected!")
                                
                                # Check for specific Outlook paths
                                if '/mapi/' in path:
                                    print("   📧 MAPI request detected!")
                                elif '/autodiscover/' in path:
                                    print("   🔍 Autodiscover request detected!")
                                elif '/ews/' in path:
                                    print("   📨 EWS request detected!")
                        
                        last_log_count = current_count
                    else:
                        print(".", end="", flush=True)
                else:
                    print(f"❌ Failed to get logs: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error monitoring: {e}")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")
        print("📊 Final analysis:")
        
        try:
            # Final analysis
            response = requests.get(f"{debug_url}/outlook-requests", verify=False)
            if response.status_code == 200:
                data = response.json()
                print(f"   Total Outlook requests: {data.get('outlook_requests', 0)}")
                
                if data.get('logs'):
                    print("\n📋 All Outlook requests during monitoring:")
                    for log in data['logs']:
                        timestamp = log.get('timestamp', 'Unknown')
                        user_agent = log.get('user_agent', 'Unknown')
                        path = log.get('path', 'Unknown')
                        method = log.get('method', 'Unknown')
                        auth_header = log.get('authorization', '')
                        
                        print(f"   {timestamp} | {method} {path}")
                        print(f"      User-Agent: {user_agent}")
                        if auth_header:
                            print(f"      Auth: {auth_header[:50]}...")
                        print()
        except Exception as e:
            print(f"❌ Error in final analysis: {e}")

if __name__ == "__main__":
    monitor_outlook_communication()
