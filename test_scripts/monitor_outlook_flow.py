#!/usr/bin/env python3
"""
Monitor Outlook Communication Flow
Track what happens after JSON autodiscover response
"""

import time
import os
import json
from datetime import datetime

def monitor_log_files():
    """Monitor log files for Outlook communication patterns"""
    
    print("🔍 MONITORING OUTLOOK COMMUNICATION FLOW")
    print("=" * 60)
    
    # Log file paths
    autodiscover_log = "logs/web/autodiscover/autodiscover.log"
    mapi_log = "logs/web/mapi/mapi.log"
    
    # Get initial file sizes
    try:
        autodiscover_size = os.path.getsize(autodiscover_log) if os.path.exists(autodiscover_log) else 0
        mapi_size = os.path.getsize(mapi_log) if os.path.exists(mapi_log) else 0
    except:
        autodiscover_size = 0
        mapi_size = 0
    
    print(f"📊 Initial log sizes:")
    print(f"   Autodiscover: {autodiscover_size} bytes")
    print(f"   MAPI: {mapi_size} bytes")
    
    print(f"\n⏰ Monitoring for 60 seconds...")
    print(f"   Start time: {datetime.now().isoformat()}")
    print(f"   Please try setting up Outlook account now!")
    print(f"   Press Ctrl+C to stop early")
    
    start_time = time.time()
    last_autodiscover_size = autodiscover_size
    last_mapi_size = mapi_size
    
    try:
        while time.time() - start_time < 60:
            time.sleep(2)
            
            # Check for new autodiscover activity
            try:
                current_autodiscover_size = os.path.getsize(autodiscover_log) if os.path.exists(autodiscover_log) else 0
                if current_autodiscover_size > last_autodiscover_size:
                    print(f"\n🆕 New Autodiscover activity detected!")
                    print(f"   Size change: {last_autodiscover_size} -> {current_autodiscover_size} bytes")
                    
                    # Read new lines
                    with open(autodiscover_log, 'r') as f:
                        lines = f.readlines()
                        new_lines = lines[last_autodiscover_size//100:]  # Approximate
                        for line in new_lines[-3:]:  # Show last 3 lines
                            try:
                                data = json.loads(line.strip())
                                event = data.get('event', 'unknown')
                                timestamp = data.get('ts', 'unknown')
                                print(f"   📍 {timestamp} | {event}")
                            except:
                                print(f"   📍 {line.strip()}")
                    
                    last_autodiscover_size = current_autodiscover_size
                    
            except Exception as e:
                print(f"   ❌ Error reading autodiscover log: {e}")
            
            # Check for new MAPI activity
            try:
                current_mapi_size = os.path.getsize(mapi_log) if os.path.exists(mapi_log) else 0
                if current_mapi_size > last_mapi_size:
                    print(f"\n🆕 New MAPI activity detected!")
                    print(f"   Size change: {last_mapi_size} -> {current_mapi_size} bytes")
                    
                    # Read new lines
                    with open(mapi_log, 'r') as f:
                        lines = f.readlines()
                        new_lines = lines[last_mapi_size//100:]  # Approximate
                        for line in new_lines[-3:]:  # Show last 3 lines
                            try:
                                data = json.loads(line.strip())
                                event = data.get('event', 'unknown')
                                timestamp = data.get('ts', 'unknown')
                                print(f"   📍 {timestamp} | {event}")
                            except:
                                print(f"   📍 {line.strip()}")
                    
                    last_mapi_size = current_mapi_size
                    
            except Exception as e:
                print(f"   ❌ Error reading MAPI log: {e}")
            
            print(".", end="", flush=True)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️ Monitoring stopped by user")
    
    # Final analysis
    try:
        final_autodiscover_size = os.path.getsize(autodiscover_log) if os.path.exists(autodiscover_log) else 0
        final_mapi_size = os.path.getsize(mapi_log) if os.path.exists(mapi_log) else 0
    except:
        final_autodiscover_size = 0
        final_mapi_size = 0
    
    print(f"\n📊 Final log sizes:")
    print(f"   Autodiscover: {final_autodiscover_size} bytes")
    print(f"   MAPI: {final_mapi_size} bytes")
    
    print(f"\n🔍 Analysis:")
    autodiscover_activity = final_autodiscover_size > autodiscover_size
    mapi_activity = final_mapi_size > mapi_size
    
    if autodiscover_activity and not mapi_activity:
        print("   ❌ Outlook is making autodiscover requests but NOT proceeding to MAPI")
        print("   💡 This suggests the JSON response is not triggering MAPI negotiation")
        print("   💡 Possible causes:")
        print("      - JSON response format issue")
        print("      - Missing critical fields")
        print("      - Outlook 2021 compatibility issue")
        print("      - Network/SSL issues")
    elif autodiscover_activity and mapi_activity:
        print("   ✅ Outlook is proceeding to MAPI negotiation")
        print("   💡 Check MAPI logs for authentication issues")
    elif not autodiscover_activity:
        print("   ❌ No autodiscover activity detected")
        print("   💡 Outlook may not be reaching the server")
    else:
        print("   ❓ Unexpected activity pattern")

def analyze_recent_logs():
    """Analyze recent log entries for patterns"""
    
    print(f"\n📋 ANALYZING RECENT LOG ENTRIES")
    print("=" * 60)
    
    # Analyze autodiscover log
    try:
        with open("logs/web/autodiscover/autodiscover.log", 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-10:]  # Last 10 lines
            
            print(f"📋 Recent Autodiscover Activity:")
            for line in recent_lines:
                try:
                    data = json.loads(line.strip())
                    event = data.get('event', 'unknown')
                    timestamp = data.get('ts', 'unknown')
                    details = data.get('details', {})
                    
                    if event == 'json_request':
                        email = details.get('email', 'unknown')
                        ua = details.get('ua', 'unknown')
                        print(f"   📍 {timestamp} | JSON Request from {email}")
                        print(f"      User-Agent: {ua}")
                    elif event == 'json_response':
                        protocol = details.get('protocol', 'unknown')
                        print(f"   📍 {timestamp} | JSON Response ({protocol})")
                        
                except:
                    print(f"   📍 {line.strip()}")
                    
    except Exception as e:
        print(f"   ❌ Error reading autodiscover log: {e}")
    
    # Analyze MAPI log
    try:
        with open("logs/web/mapi/mapi.log", 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-10:]  # Last 10 lines
            
            print(f"\n📋 Recent MAPI Activity:")
            for line in recent_lines:
                try:
                    data = json.loads(line.strip())
                    event = data.get('event', 'unknown')
                    timestamp = data.get('ts', 'unknown')
                    print(f"   📍 {timestamp} | {event}")
                except:
                    print(f"   📍 {line.strip()}")
                    
    except Exception as e:
        print(f"   ❌ Error reading MAPI log: {e}")

if __name__ == "__main__":
    print(f"🚀 Starting Outlook Flow Monitor")
    print(f"⏰ Time: {datetime.now().isoformat()}")
    
    analyze_recent_logs()
    monitor_log_files()
    
    print(f"\n✅ Monitoring complete!")
