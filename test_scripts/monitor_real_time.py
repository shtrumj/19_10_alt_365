#!/usr/bin/env python3
"""
Real-time monitoring of Outlook communication
"""

import time
import json
import os
from datetime import datetime

def monitor_real_time():
    """Monitor logs in real-time for Outlook activity"""
    
    print("🔍 Real-time Outlook Communication Monitor")
    print("=" * 60)
    print("📋 Instructions:")
    print("   1. Start this monitor")
    print("   2. Try setting up Outlook account")
    print("   3. Watch for new activity")
    print("   4. Press Ctrl+C to stop")
    print()
    
    mapi_log = "/Users/jonathanshtrum/Downloads/365/logs/web/mapi/mapi.log"
    autodiscover_log = "/Users/jonathanshtrum/Downloads/365/logs/web/autodiscover/autodiscover.log"
    
    # Get initial file sizes
    mapi_size = os.path.getsize(mapi_log) if os.path.exists(mapi_log) else 0
    autodiscover_size = os.path.getsize(autodiscover_log) if os.path.exists(autodiscover_log) else 0
    
    print(f"📊 Starting monitoring...")
    print(f"   MAPI log size: {mapi_size} bytes")
    print(f"   Autodiscover log size: {autodiscover_size} bytes")
    print()
    
    try:
        while True:
            time.sleep(2)
            
            # Check MAPI log
            if os.path.exists(mapi_log):
                current_mapi_size = os.path.getsize(mapi_log)
                if current_mapi_size > mapi_size:
                    print(f"🆕 New MAPI activity detected!")
                    mapi_size = current_mapi_size
                    
                    # Read new lines
                    with open(mapi_log, 'r') as f:
                        lines = f.readlines()
                        for line in lines[-5:]:  # Last 5 lines
                            try:
                                log_entry = json.loads(line.strip())
                                timestamp = log_entry.get('ts', 'Unknown')
                                event = log_entry.get('event', 'Unknown')
                                user_agent = log_entry.get('ua', '') or log_entry.get('user_agent', '')
                                
                                print(f"   📍 {timestamp} | {event}")
                                
                                if any(keyword in user_agent.lower() for keyword in ['outlook', 'microsoft office']):
                                    print(f"   🎯 OUTLOOK DETECTED: {user_agent}")
                                    
                                    # Check for NTLM flow
                                    if 'ntlm' in event.lower():
                                        stage = log_entry.get('stage', '')
                                        print(f"   🔐 NTLM {stage}")
                                        
                                        if stage == 'type1_received':
                                            print(f"   ⚠️  Type1 received - waiting for Type3...")
                                        elif stage == 'type3_received':
                                            print(f"   ✅ Type3 received - authentication successful!")
                                        elif stage == 'type2_sent':
                                            print(f"   📤 Type2 sent - challenge issued")
                                
                                # Check for authentication
                                auth_header = log_entry.get('authorization', '')
                                if auth_header and 'ntlm' in auth_header.lower():
                                    print(f"   🔐 NTLM Auth: {auth_header[:50]}...")
                                    
                                    if 'TlRMTVNTUAAB' in auth_header:
                                        print(f"   📥 Type1 NTLM request")
                                    elif 'TlRMTVNTUAAD' in auth_header:
                                        print(f"   📥 Type3 NTLM request")
                                
                            except json.JSONDecodeError:
                                continue
            
            # Check Autodiscover log
            if os.path.exists(autodiscover_log):
                current_autodiscover_size = os.path.getsize(autodiscover_log)
                if current_autodiscover_size > autodiscover_size:
                    print(f"🆕 New Autodiscover activity detected!")
                    autodiscover_size = current_autodiscover_size
                    
                    # Read new lines
                    with open(autodiscover_log, 'r') as f:
                        lines = f.readlines()
                        for line in lines[-3:]:  # Last 3 lines
                            try:
                                log_entry = json.loads(line.strip())
                                timestamp = log_entry.get('ts', 'Unknown')
                                event = log_entry.get('event', 'Unknown')
                                user_agent = log_entry.get('ua', '') or log_entry.get('user_agent', '')
                                
                                print(f"   📍 {timestamp} | {event}")
                                
                                if any(keyword in user_agent.lower() for keyword in ['outlook', 'microsoft office']):
                                    print(f"   🎯 OUTLOOK AUTODISCOVER: {user_agent}")
                                
                            except json.JSONDecodeError:
                                continue
            
            print(".", end="", flush=True)
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 Monitoring stopped")
        print(f"📊 Final log sizes:")
        print(f"   MAPI: {os.path.getsize(mapi_log) if os.path.exists(mapi_log) else 0} bytes")
        print(f"   Autodiscover: {os.path.getsize(autodiscover_log) if os.path.exists(autodiscover_log) else 0} bytes")

if __name__ == "__main__":
    monitor_real_time()
