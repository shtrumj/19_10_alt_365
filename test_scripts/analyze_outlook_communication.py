#!/usr/bin/env python3
"""
Analyze Outlook communication from existing logs
"""

import json
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter

def analyze_mapi_logs():
    """Analyze MAPI logs for Outlook communication patterns"""
    
    print("🔍 Analyzing MAPI Communication Logs")
    print("=" * 60)
    
    log_file = "/Users/jonathanshtrum/Downloads/365/logs/web/mapi/mapi.log"
    
    if not os.path.exists(log_file):
        print(f"❌ Log file not found: {log_file}")
        return
    
    outlook_requests = []
    ntlm_flows = []
    authentication_attempts = []
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Check for Outlook requests
                    user_agent = log_entry.get('ua', '') or log_entry.get('user_agent', '')
                    if any(keyword in user_agent.lower() for keyword in ['outlook', 'microsoft office', 'mapi']):
                        outlook_requests.append(log_entry)
                    
                    # Check for NTLM flows
                    if 'ntlm' in log_entry.get('event', '').lower():
                        ntlm_flows.append(log_entry)
                    
                    # Check for authentication
                    if 'auth' in log_entry.get('event', '').lower():
                        authentication_attempts.append(log_entry)
                        
                except json.JSONDecodeError:
                    continue
    
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return
    
    print(f"📊 Analysis Results:")
    print(f"   Total log entries analyzed")
    print(f"   Outlook requests: {len(outlook_requests)}")
    print(f"   NTLM flows: {len(ntlm_flows)}")
    print(f"   Authentication attempts: {len(authentication_attempts)}")
    
    # Analyze Outlook requests
    if outlook_requests:
        print(f"\n📋 Outlook Request Analysis:")
        
        # Group by user agent
        user_agents = Counter([req.get('ua', '') or req.get('user_agent', '') for req in outlook_requests])
        print(f"   User Agents:")
        for ua, count in user_agents.most_common(5):
            print(f"     {count}x {ua}")
        
        # Group by event type
        events = Counter([req.get('event', '') for req in outlook_requests])
        print(f"   Event Types:")
        for event, count in events.most_common(10):
            print(f"     {count}x {event}")
        
        # Check for recent activity
        recent_requests = [req for req in outlook_requests if is_recent(req.get('ts', ''))]
        print(f"   Recent requests (last hour): {len(recent_requests)}")
        
        if recent_requests:
            print(f"   Latest Outlook requests:")
            for req in recent_requests[-5:]:
                timestamp = req.get('ts', 'Unknown')
                event = req.get('event', 'Unknown')
                user_agent = req.get('ua', '') or req.get('user_agent', 'Unknown')
                print(f"     {timestamp} | {event} | {user_agent[:50]}...")
    
    # Analyze NTLM flows
    if ntlm_flows:
        print(f"\n🔐 NTLM Flow Analysis:")
        
        # Group by stage
        stages = Counter([flow.get('stage', '') for flow in ntlm_flows])
        print(f"   NTLM Stages:")
        for stage, count in stages.most_common():
            print(f"     {count}x {stage}")
        
        # Check for Type3 authentication
        type3_flows = [flow for flow in ntlm_flows if flow.get('stage') == 'type3_received']
        print(f"   Type3 authentications: {len(type3_flows)}")
        
        if type3_flows:
            print(f"   ✅ NTLM authentication is working!")
            for flow in type3_flows[-3:]:
                timestamp = flow.get('ts', 'Unknown')
                token_len = flow.get('token_len', 'Unknown')
                print(f"     {timestamp} | Token length: {token_len}")
        else:
            print(f"   ❌ No Type3 authentications found - this is the problem!")
    
    # Analyze authentication attempts
    if authentication_attempts:
        print(f"\n🔑 Authentication Analysis:")
        
        # Group by auth type
        auth_types = Counter([attempt.get('auth_type', '') for attempt in authentication_attempts])
        print(f"   Authentication Types:")
        for auth_type, count in auth_types.most_common():
            print(f"     {count}x {auth_type}")
        
        # Check for successful authentications
        successful_auths = [attempt for attempt in authentication_attempts 
                           if attempt.get('event') in ['ntlm_authenticated', 'auth_success']]
        print(f"   Successful authentications: {len(successful_auths)}")
        
        if not successful_auths:
            print(f"   ❌ No successful authentications found!")
    
    # Check for stuck patterns
    print(f"\n🔍 Stuck Pattern Analysis:")
    
    # Look for Type1 without Type3
    type1_requests = [flow for flow in ntlm_flows if flow.get('stage') == 'type1_received']
    type3_requests = [flow for flow in ntlm_flows if flow.get('stage') == 'type3_received']
    
    print(f"   Type1 requests: {len(type1_requests)}")
    print(f"   Type3 requests: {len(type3_requests)}")
    
    if len(type1_requests) > len(type3_requests):
        print(f"   ❌ PROBLEM: {len(type1_requests) - len(type3_requests)} Type1 requests without Type3 responses!")
        print(f"   This means Outlook is sending Type1 but not completing the NTLM flow")
        
        # Show recent Type1 requests without Type3
        recent_type1 = [req for req in type1_requests if is_recent(req.get('ts', ''))]
        print(f"   Recent Type1 requests without completion:")
        for req in recent_type1[-3:]:
            timestamp = req.get('ts', 'Unknown')
            request_id = req.get('request_id', 'Unknown')
            print(f"     {timestamp} | Request ID: {request_id}")
    else:
        print(f"   ✅ NTLM flow appears to be working correctly")

def is_recent(timestamp_str):
    """Check if timestamp is within the last hour"""
    try:
        # Parse ISO timestamp
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timestamp.tzinfo)
        return (now - timestamp).total_seconds() < 3600  # Last hour
    except:
        return False

def analyze_autodiscover_logs():
    """Analyze autodiscover logs"""
    
    print(f"\n🔍 Analyzing Autodiscover Logs")
    print("=" * 60)
    
    log_file = "/Users/jonathanshtrum/Downloads/365/logs/web/autodiscover/autodiscover.log"
    
    if not os.path.exists(log_file):
        print(f"❌ Autodiscover log file not found: {log_file}")
        return
    
    autodiscover_requests = []
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    autodiscover_requests.append(log_entry)
                except json.JSONDecodeError:
                    continue
    
    except Exception as e:
        print(f"❌ Error reading autodiscover log file: {e}")
        return
    
    print(f"📊 Autodiscover Analysis:")
    print(f"   Total requests: {len(autodiscover_requests)}")
    
    # Check for recent requests
    recent_requests = [req for req in autodiscover_requests if is_recent(req.get('ts', ''))]
    print(f"   Recent requests (last hour): {len(recent_requests)}")
    
    if recent_requests:
        print(f"   Latest autodiscover requests:")
        for req in recent_requests[-5:]:
            timestamp = req.get('ts', 'Unknown')
            event = req.get('event', 'Unknown')
            ip = req.get('ip', 'Unknown')
            print(f"     {timestamp} | {event} | IP: {ip}")
    
    # Check for Outlook user agents
    outlook_autodiscover = [req for req in autodiscover_requests 
                           if any(keyword in req.get('ua', '').lower() 
                                 for keyword in ['outlook', 'microsoft office'])]
    
    print(f"   Outlook autodiscover requests: {len(outlook_autodiscover)}")
    
    if outlook_autodiscover:
        print(f"   ✅ Outlook is using autodiscover!")
        for req in outlook_autodiscover[-3:]:
            timestamp = req.get('ts', 'Unknown')
            user_agent = req.get('ua', 'Unknown')
            print(f"     {timestamp} | {user_agent}")
    else:
        print(f"   ❌ No Outlook autodiscover requests found")

def main():
    """Main analysis function"""
    
    print("🔍 Outlook Communication Analysis")
    print("=" * 60)
    print(f"Analysis started at: {datetime.now().isoformat()}")
    print()
    
    # Analyze MAPI logs
    analyze_mapi_logs()
    
    # Analyze autodiscover logs
    analyze_autodiscover_logs()
    
    print(f"\n📋 Summary:")
    print(f"   This analysis shows the communication patterns between Outlook and the server")
    print(f"   Look for patterns like:")
    print(f"   - Outlook requests without Type3 NTLM responses")
    print(f"   - Autodiscover requests from Outlook")
    print(f"   - Authentication failures")
    print(f"   - Missing communication steps")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Try setting up Outlook account while this analysis runs")
    print(f"   2. Look for new entries in the logs")
    print(f"   3. Identify where the communication stops")
    print(f"   4. Check if Outlook is reaching the server at all")

if __name__ == "__main__":
    main()
