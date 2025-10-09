#!/usr/bin/env python3
"""
Test WebSocket router directly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

def test_websocket_router():
    """Test if WebSocket router is working"""
    print("🧪 Testing WebSocket router directly...")
    
    client = TestClient(app)
    
    # Test the simple test endpoint
    try:
        response = client.get("/ws/test")
        print(f"   /ws/test - Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
            print("   ✅ WebSocket router is working!")
        else:
            print(f"   ❌ WebSocket router failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error testing WebSocket router: {e}")
    
    # Test connections endpoint
    try:
        response = client.get("/ws/connections")
        print(f"   /ws/connections - Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   ❌ Connections endpoint failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Error testing connections endpoint: {e}")

if __name__ == "__main__":
    test_websocket_router()
