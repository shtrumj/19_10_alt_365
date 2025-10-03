#!/bin/bash
# Real-time Push Notification Monitor

echo "📡 Monitoring ActiveSync Push Notifications"
echo "════════════════════════════════════════════"
echo ""
echo "Watching for:"
echo "  • Ping connections"
echo "  • Push notification triggers"
echo "  • Email arrivals"
echo ""
echo "Press Ctrl+C to stop"
echo ""

tail -f /Users/jonathanshtrum/Downloads/365/logs/activesync/activesync.log | while read line; do
    # Check if line contains relevant events
    if echo "$line" | grep -q '"event": "ping_start"'; then
        echo "✅ $(date '+%H:%M:%S') - iPhone connected with Ping (Push mode)"
        # Extract heartbeat interval
        interval=$(echo "$line" | grep -o '"heartbeat_interval": [0-9]*' | grep -o '[0-9]*')
        echo "   Heartbeat: ${interval}s (~$((interval/60)) minutes)"
    fi
    
    if echo "$line" | grep -q '"event": "ping_changes_detected"'; then
        echo "📧 $(date '+%H:%M:%S') - NEW EMAIL DETECTED - Push notification sent!"
        elapsed=$(echo "$line" | grep -o '"elapsed_seconds": [0-9]*' | grep -o '[0-9]*')
        echo "   Response time: ${elapsed}s"
    fi
    
    if echo "$line" | grep -q '"event": "ping_timeout"'; then
        echo "⏱️  $(date '+%H:%M:%S') - Ping timeout (normal - iPhone will reconnect)"
    fi
    
    if echo "$line" | grep -q '"event": "ping_complete"'; then
        echo "✓  $(date '+%H:%M:%S') - Ping completed"
    fi
    
    if echo "$line" | grep -q '📱 Triggered ActiveSync push notification'; then
        echo "🔔 $(date '+%H:%M:%S') - SMTP triggered push notification"
    fi
done
