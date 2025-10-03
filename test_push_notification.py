#!/usr/bin/env python3
"""
Test Push Notification System

This script simulates what happens when a new email arrives and triggers
the push notification system to notify connected devices.
"""

import asyncio
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_push_notification():
    """Test the push notification system"""
    from app.push_notifications import push_manager, notify_new_email
    
    print("🧪 Testing Push Notification System\n")
    
    # Simulate user ID 1 (yonatan@shtrum.com)
    user_id = 1
    folder_id = "1"  # Inbox
    
    print(f"📊 Current active Ping connections:")
    total_connections = push_manager.get_active_connections_count()
    user_connections = push_manager.get_user_connections_count(user_id)
    print(f"   Total: {total_connections}")
    print(f"   For user {user_id}: {user_connections}")
    
    if user_connections == 0:
        print(f"\n⚠️  No active Ping connections for user {user_id}!")
        print(f"   This means the iPhone is NOT in Push mode.")
        print(f"   To enable Push:")
        print(f"   1. Open iPhone Settings → Mail → Accounts → Fetch New Data")
        print(f"   2. Turn ON 'Push' at the top")
        print(f"   3. Tap your account and select 'Push'")
        print(f"\n   Then run this script again to test.")
        return
    
    print(f"\n✅ Found {user_connections} active Ping connection(s)!")
    print(f"   Simulating new email arrival...")
    
    # Trigger notification
    await notify_new_email(user_id, folder_id)
    
    print(f"\n✅ Push notification triggered successfully!")
    print(f"   All {user_connections} Ping connection(s) have been notified.")
    print(f"   The iPhone should receive the notification instantly.")
    
    # Give a moment for the notification to be processed
    await asyncio.sleep(1)
    
    print(f"\n📱 Check your iPhone - it should have received the push notification!")


async def monitor_connections():
    """Monitor Ping connections in real-time"""
    from app.push_notifications import push_manager
    
    print("📡 Monitoring Ping Connections (Ctrl+C to stop)\n")
    
    previous_count = 0
    try:
        while True:
            total = push_manager.get_active_connections_count()
            
            if total != previous_count:
                if total > previous_count:
                    print(f"✅ New Ping connection! Total: {total}")
                elif total < previous_count:
                    print(f"❌ Ping connection closed. Total: {total}")
                else:
                    print(f"📊 Active connections: {total}")
                
                previous_count = total
            
            await asyncio.sleep(2)
            
    except KeyboardInterrupt:
        print(f"\n\n📊 Final count: {push_manager.get_active_connections_count()} active connections")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        asyncio.run(monitor_connections())
    else:
        asyncio.run(test_push_notification())

