#!/usr/bin/env python3
"""
Unit tests for iOS ActiveSync strategy

Tests iOS-specific behavior including:
- Immediate item delivery on initial sync
- Window size limits
- Truncation strategy for different body types
- Two-phase commit requirement
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.strategies.ios_strategy import IOSStrategy


def test_ios_accepts_items_immediately():
    """Test that iOS accepts items immediately on any SyncKey"""
    strategy = IOSStrategy()
    assert strategy.needs_empty_initial_response("0") == False
    assert strategy.needs_empty_initial_response("1") == False
    assert strategy.needs_empty_initial_response("2") == False
    print("✅ iOS immediate item delivery test passed")


def test_ios_window_size():
    """Test iOS window size settings"""
    strategy = IOSStrategy()
    assert strategy.get_max_window_size() == 100
    assert strategy.get_default_window_size() == 50
    print("✅ iOS window size test passed")


def test_ios_truncation_honors_client():
    """Test that iOS truncation honors client's request for Type=1/2"""
    strategy = IOSStrategy()

    # Type 1 (plain) - honor client's request (iOS typically requests 32KB)
    assert strategy.get_truncation_strategy(1, 32768, False) == 32768
    assert strategy.get_truncation_strategy(1, 10000, False) == 10000

    # Type 2 (HTML) - honor client's request
    assert strategy.get_truncation_strategy(2, 32768, False) == 32768

    print("✅ iOS Type=1/2 truncation test passed")


def test_ios_truncation_caps_mime():
    """Test that iOS caps MIME at 512KB"""
    strategy = IOSStrategy()

    # Type 4 (MIME) - capped at 512KB
    assert strategy.get_truncation_strategy(4, 1000000, False) == 512000
    assert strategy.get_truncation_strategy(4, 100000, False) == 100000
    assert strategy.get_truncation_strategy(4, None, False) == 512000

    print("✅ iOS Type=4 MIME truncation test passed")


def test_ios_body_preference_order():
    """Test iOS body type preference order"""
    strategy = IOSStrategy()
    prefs = strategy.get_body_type_preference_order()

    assert prefs == [1, 2, 4], "iOS should prefer plain, then HTML, then MIME"
    assert prefs[0] == 1, "First preference should be plain text"

    print("✅ iOS body preference order test passed")


def test_ios_pending_confirmation():
    """Test that iOS uses two-phase commit"""
    strategy = IOSStrategy()
    assert strategy.should_use_pending_confirmation() == True
    print("✅ iOS pending confirmation test passed")


def test_ios_client_name():
    """Test client name helper"""
    strategy = IOSStrategy()
    assert strategy.get_client_name() == "IOS"
    print("✅ iOS client name test passed")


def run_all_tests():
    """Run all iOS strategy tests"""
    print("\n" + "=" * 60)
    print("iOS ActiveSync Strategy Tests")
    print("=" * 60 + "\n")

    tests = [
        test_ios_accepts_items_immediately,
        test_ios_window_size,
        test_ios_truncation_honors_client,
        test_ios_truncation_caps_mime,
        test_ios_body_preference_order,
        test_ios_pending_confirmation,
        test_ios_client_name,
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
