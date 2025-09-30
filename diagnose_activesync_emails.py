#!/usr/bin/env python3
"""
ActiveSync Email Download Diagnostic Script
Analyzes why emails are not being downloaded despite ActiveSync connection
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta

def analyze_activesync_logs():
    """Analyze ActiveSync logs to identify the issue"""
    print("🔍 ANALYZING ACTIVESYNC LOGS")
    print("=" * 50)
    
    log_file = "logs/activesync/activesync.log"
    if not os.path.exists(log_file):
        print("❌ ActiveSync log file not found")
        return
    
    # Read recent logs
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    recent_lines = lines[-50:]  # Last 50 lines
    
    # Analyze patterns
    rate_limits = 0
    foldersync_requests = 0
    sync_requests = 0
    successful_syncs = 0
    
    for line in recent_lines:
        try:
            data = json.loads(line.strip())
            event = data.get('event', '')
            
            if event == 'rate_limit_exceeded':
                rate_limits += 1
            elif event == 'foldersync_initial' or event == 'foldersync_empty':
                foldersync_requests += 1
            elif event == 'sync_response' or event == 'sync_empty':
                sync_requests += 1
                successful_syncs += 1
        except:
            continue
    
    print(f"📊 Recent Activity Analysis:")
    print(f"   Rate Limit Exceeded: {rate_limits}")
    print(f"   FolderSync Requests: {foldersync_requests}")
    print(f"   Email Sync Requests: {sync_requests}")
    print(f"   Successful Syncs: {successful_syncs}")
    
    if rate_limits > 20:
        print("❌ ISSUE: Client is hitting rate limits excessively")
        print("   → Client is making too many requests too quickly")
        print("   → This prevents proper sync completion")
    
    if foldersync_requests > 0 and sync_requests == 0:
        print("❌ ISSUE: Client is stuck in foldersync loop")
        print("   → Client completes foldersync but never proceeds to email sync")
        print("   → This indicates a foldersync completion issue")
    
    if sync_requests == 0:
        print("❌ ISSUE: No email sync requests detected")
        print("   → Client never attempts to sync emails")
        print("   → This suggests foldersync is not completing properly")

def check_database_emails():
    """Check if there are emails in the database"""
    print("\n📧 CHECKING DATABASE EMAILS")
    print("=" * 50)
    
    db_path = "data/email_system.db"
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = 'yonatan'")
        user_result = cursor.fetchone()
        if not user_result:
            print("❌ User 'yonatan' not found in database")
            return
        
        user_id = user_result[0]
        
        # Count emails for user
        cursor.execute("SELECT COUNT(*) FROM emails WHERE recipient_id = ?", (user_id,))
        email_count = cursor.fetchone()[0]
        
        print(f"📊 Database Analysis:")
        print(f"   User ID: {user_id}")
        print(f"   Total Emails: {email_count}")
        
        if email_count > 0:
            print("✅ Emails are available in database")
            
            # Get recent emails
            cursor.execute("""
                SELECT subject, created_at 
                FROM emails 
                WHERE recipient_id = ? 
                ORDER BY created_at DESC 
                LIMIT 5
            """, (user_id,))
            
            recent_emails = cursor.fetchall()
            print(f"\n📬 Recent Emails:")
            for subject, created_at in recent_emails:
                print(f"   • {subject} ({created_at})")
        else:
            print("❌ No emails found in database")
            print("   → This could be why no emails are syncing")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

def check_activesync_configuration():
    """Check ActiveSync configuration"""
    print("\n⚙️ CHECKING ACTIVESYNC CONFIGURATION")
    print("=" * 50)
    
    # Check if ActiveSync endpoint is accessible
    import requests
    try:
        response = requests.options("https://owa.shtrum.com/activesync/Microsoft-Server-ActiveSync", 
                                  timeout=10, verify=False)
        print(f"✅ ActiveSync Endpoint: {response.status_code}")
        
        if response.status_code == 200:
            headers = response.headers
            print(f"   MS-Server-ActiveSync: {headers.get('ms-server-activesync', 'N/A')}")
            print(f"   MS-ASProtocolVersions: {headers.get('ms-asprotocolversions', 'N/A')}")
            print(f"   MS-ASProtocolCommands: {headers.get('ms-asprotocolcommands', 'N/A')}")
        else:
            print(f"❌ ActiveSync endpoint returned {response.status_code}")
            
    except Exception as e:
        print(f"❌ Cannot reach ActiveSync endpoint: {e}")

def provide_recommendations():
    """Provide recommendations to fix the issue"""
    print("\n💡 RECOMMENDATIONS")
    print("=" * 50)
    
    print("🔧 IMMEDIATE FIXES:")
    print("1. **Reset Rate Limits**: Clear the rate limit cache")
    print("2. **Fix Foldersync Loop**: Ensure foldersync completes properly")
    print("3. **Increase Rate Limits**: Allow more requests per minute")
    print("4. **Check Client State**: Reset client sync state")
    
    print("\n🔍 DEBUGGING STEPS:")
    print("1. **Monitor Logs**: Watch for new activity after fixes")
    print("2. **Test Manually**: Try manual ActiveSync requests")
    print("3. **Check Client**: Verify Outlook is configured correctly")
    print("4. **Database Check**: Ensure emails exist and are accessible")
    
    print("\n📋 EXPECTED BEHAVIOR:")
    print("1. Client should complete foldersync once")
    print("2. Client should then proceed to email sync")
    print("3. Email sync should return actual emails")
    print("4. Client should maintain sync state properly")

def main():
    print("🚀 ACTIVESYNC EMAIL DOWNLOAD DIAGNOSTIC")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print()
    
    analyze_activesync_logs()
    check_database_emails()
    check_activesync_configuration()
    provide_recommendations()
    
    print("\n" + "=" * 60)
    print("✅ DIAGNOSTIC COMPLETE")

if __name__ == "__main__":
    main()
