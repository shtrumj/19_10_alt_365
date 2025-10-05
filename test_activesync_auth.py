#!/usr/bin/env python3
"""
Test script to verify ActiveSync authentication is working
"""
import base64
import json
from datetime import datetime

import requests


def test_activesync_auth():
    """Test ActiveSync authentication flow"""

    # Test credentials
    username = "yonatan@shtrum.com"  # Real user from database
    password = "Gib$0n579!"  # Real password

    # Base URL
    base_url = "https://owa.shtrum.com"  # Change this to your server URL

    # Create basic auth header
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded_credentials}"

    print(f"Testing ActiveSync authentication for {username}")
    print(f"Auth header: {auth_header[:30]}...")

    # Test 1: OPTIONS request (should work without auth)
    print("\n1. Testing OPTIONS request...")
    try:
        response = requests.options(
            f"{base_url}/Microsoft-Server-ActiveSync",
            headers={
                "User-Agent": "Apple-iPhone16C2/2301.355",
                "Host": "owa.shtrum.com",
            },
            timeout=10,
        )
        print(f"OPTIONS Status: {response.status_code}")
        print(f"OPTIONS Headers: {dict(response.headers)}")

        if response.status_code == 200:
            print("✓ OPTIONS request successful")
        else:
            print("✗ OPTIONS request failed")

    except Exception as e:
        print(f"✗ OPTIONS request error: {e}")

    # Test 2: POST request with authentication
    print("\n2. Testing POST request with authentication...")
    try:
        response = requests.post(
            f"{base_url}/Microsoft-Server-ActiveSync",
            headers={
                "Authorization": auth_header,
                "User-Agent": "Apple-iPhone16C2/2301.355",
                "Host": "owa.shtrum.com",
                "Content-Type": "application/vnd.ms-sync.wbxml",
                "MS-ASProtocolVersion": "16.1",
            },
            params={
                "Cmd": "Provision",
                "DeviceId": "test-device-123",
                "DeviceType": "SmartPhone",
            },
            data=b"\x03\x01\x00\x00\x00",  # Minimal WBXML
            timeout=10,
        )
        print(f"POST Status: {response.status_code}")
        print(f"POST Headers: {dict(response.headers)}")
        print(f"POST Content: {response.content[:100]}...")

        if response.status_code == 200:
            print("✓ POST request with auth successful")
        elif response.status_code == 401:
            print("✗ POST request failed - Authentication required")
        else:
            print(f"✗ POST request failed with status {response.status_code}")

    except Exception as e:
        print(f"✗ POST request error: {e}")

    # Test 3: POST request without authentication
    print("\n3. Testing POST request without authentication...")
    try:
        response = requests.post(
            f"{base_url}/Microsoft-Server-ActiveSync",
            headers={
                "User-Agent": "Apple-iPhone16C2/2301.355",
                "Host": "owa.shtrum.com",
                "Content-Type": "application/vnd.ms-sync.wbxml",
                "MS-ASProtocolVersion": "16.1",
            },
            params={
                "Cmd": "Provision",
                "DeviceId": "test-device-123",
                "DeviceType": "SmartPhone",
            },
            data=b"\x03\x01\x00\x00\x00",  # Minimal WBXML
            timeout=10,
        )
        print(f"POST (no auth) Status: {response.status_code}")
        print(f"POST (no auth) Headers: {dict(response.headers)}")

        if response.status_code == 401:
            print("✓ POST request correctly requires authentication")
        else:
            print(
                f"✗ POST request should require authentication, got {response.status_code}"
            )

    except Exception as e:
        print(f"✗ POST request (no auth) error: {e}")


if __name__ == "__main__":
    test_activesync_auth()
