#!/usr/bin/env python3
"""
Unit tests for ActiveSync strategy factory

Tests client detection and strategy selection logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.strategies.android_strategy import AndroidStrategy
from activesync.strategies.factory import detect_client_type, get_activesync_strategy
from activesync.strategies.ios_strategy import IOSStrategy
from activesync.strategies.outlook_strategy import OutlookStrategy


def test_factory_detects_outlook_by_user_agent():
    """Test Outlook detection via User-Agent"""
    strategy = get_activesync_strategy("Outlook/16.0 (16.0.14334.20244; x64)", "")
    assert isinstance(strategy, OutlookStrategy)
    print("✅ Outlook detection via User-Agent test passed")


def test_factory_detects_outlook_by_device_type():
    """Test Outlook detection via DeviceType"""
    strategy = get_activesync_strategy("", "WindowsOutlook15")
    assert isinstance(strategy, OutlookStrategy)
    print("✅ Outlook detection via DeviceType test passed")


def test_factory_detects_ios_iphone():
    """Test iOS detection via iPhone User-Agent"""
    strategy = get_activesync_strategy("Apple iPhone13,2", "iPhone")
    assert isinstance(strategy, IOSStrategy)
    print("✅ iOS iPhone detection test passed")


def test_factory_detects_ios_ipad():
    """Test iOS detection via iPad User-Agent"""
    strategy = get_activesync_strategy("Apple iPad8,1", "iPad")
    assert isinstance(strategy, IOSStrategy)
    print("✅ iOS iPad detection test passed")


def test_factory_detects_android():
    """Test Android detection"""
    strategy = get_activesync_strategy("Android/10.0", "Android")
    assert isinstance(strategy, AndroidStrategy)
    print("✅ Android detection test passed")


def test_factory_defaults_to_ios():
    """Test that unknown clients default to iOS strategy"""
    strategy = get_activesync_strategy("UnknownClient/1.0", "Unknown")
    assert isinstance(strategy, IOSStrategy)
    print("✅ Default to iOS strategy test passed")


def test_detect_client_type_outlook():
    """Test client type detection helper for Outlook"""
    client_type = detect_client_type("Outlook/16.0", "WindowsOutlook15")
    assert client_type == "Outlook"
    print("✅ Client type detection (Outlook) test passed")


def test_detect_client_type_ios():
    """Test client type detection helper for iOS"""
    client_type = detect_client_type("Apple iPhone13,2", "iPhone")
    assert client_type == "IOS"
    print("✅ Client type detection (iOS) test passed")


def test_detect_client_type_android():
    """Test client type detection helper for Android"""
    client_type = detect_client_type("Android/10.0", "Android")
    assert client_type == "Android"
    print("✅ Client type detection (Android) test passed")


def test_case_insensitive_detection():
    """Test that detection is case-insensitive"""
    # Lowercase outlook
    strategy1 = get_activesync_strategy("outlook/16.0", "")
    assert isinstance(strategy1, OutlookStrategy)

    # Mixed case iPhone
    strategy2 = get_activesync_strategy("iPhone", "")
    assert isinstance(strategy2, IOSStrategy)

    print("✅ Case-insensitive detection test passed")


def run_all_tests():
    """Run all strategy factory tests"""
    print("\n" + "=" * 60)
    print("ActiveSync Strategy Factory Tests")
    print("=" * 60 + "\n")

    tests = [
        test_factory_detects_outlook_by_user_agent,
        test_factory_detects_outlook_by_device_type,
        test_factory_detects_ios_iphone,
        test_factory_detects_ios_ipad,
        test_factory_detects_android,
        test_factory_defaults_to_ios,
        test_detect_client_type_outlook,
        test_detect_client_type_ios,
        test_detect_client_type_android,
        test_case_insensitive_detection,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
