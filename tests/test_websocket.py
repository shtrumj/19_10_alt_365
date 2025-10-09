#!/usr/bin/env python3
"""
Test WebSocket functionality
"""
import requests
import json
import time

def test_websocket_system():
    """Test the WebSocket system"""
    print("🧪 Testing WebSocket system...")
    
    base_url = "https://owa.shtrum.com"
    
    try:
        # Test WebSocket endpoints
        print("📡 Testing WebSocket endpoints...")
        
        # Test connection info
        response = requests.get(f"{base_url}/ws/connections", verify=False, timeout=10)
        print(f"   Connections endpoint: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Active connections: {data.get('total_connections', 0)}")
        
        # Test notification endpoint
        print("📧 Testing notification system...")
        response = requests.get(f"{base_url}/ws/test-notification/1", verify=False, timeout=10)
        print(f"   Test notification: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data.get('message', 'No message')}")
        
        # Test broadcast endpoint
        print("📢 Testing broadcast system...")
        response = requests.get(f"{base_url}/ws/test-broadcast", verify=False, timeout=10)
        print(f"   Test broadcast: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data.get('message', 'No message')}")
        
        print("✅ WebSocket system tests completed!")
        
    except Exception as e:
        print(f"❌ Error testing WebSocket system: {e}")

if __name__ == "__main__":
    test_websocket_system()
