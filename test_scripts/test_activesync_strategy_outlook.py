#!/usr/bin/env python3
"""
Unit tests for Outlook ActiveSync strategy

Tests Outlook-specific behavior including:
- Empty initial response requirement
- Window size limits
- Truncation strategy for different body types
- Two-phase commit requirement
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.strategies.outlook_strategy import OutlookStrategy


def test_outlook_needs_empty_initial():
    """Test that Outlook requires empty response on SyncKey=0"""
    strategy = OutlookStrategy()
    assert strategy.needs_empty_initial_response("0") == True
    assert strategy.needs_empty_initial_response("1") == False
    assert strategy.needs_empty_initial_response("2") == False
    print("✅ Outlook empty initial response test passed")


def test_outlook_window_size():
    """Test Outlook window size settings"""
    strategy = OutlookStrategy()
    assert strategy.get_max_window_size() == 100
    assert strategy.get_default_window_size() == 25
    print("✅ Outlook window size test passed")


def test_outlook_truncation_honors_client():
    """Test that Outlook truncation honors client's request for Type=1/2"""
    strategy = OutlookStrategy()

    # Type 1 (plain) - honor client's request
    assert strategy.get_truncation_strategy(1, 32768, False) == 32768
    assert strategy.get_truncation_strategy(1, 10000, False) == 10000

    # Type 2 (HTML) - honor client's request
    assert strategy.get_truncation_strategy(2, 32768, False) == 32768

    print("✅ Outlook Type=1/2 truncation test passed")


def test_outlook_truncation_caps_mime():
    """Test that Outlook caps MIME at 512KB"""
    strategy = OutlookStrategy()

    # Type 4 (MIME) - capped at 512KB
    assert strategy.get_truncation_strategy(4, 1000000, False) == 512000
    assert strategy.get_truncation_strategy(4, 100000, False) == 100000
    assert strategy.get_truncation_strategy(4, None, False) == 512000

    print("✅ Outlook Type=4 MIME truncation test passed")


def test_outlook_body_preference_order():
    """Test Outlook body type preference order"""
    strategy = OutlookStrategy()
    prefs = strategy.get_body_type_preference_order()

    assert prefs == [4, 1, 2], "Outlook should prefer MIME, then plain, then HTML"
    assert prefs[0] == 4, "First preference should be MIME"

    print("✅ Outlook body preference order test passed")


def test_outlook_pending_confirmation():
    """Test that Outlook uses two-phase commit"""
    strategy = OutlookStrategy()
    assert strategy.should_use_pending_confirmation() == True
    print("✅ Outlook pending confirmation test passed")


def test_outlook_client_name():
    """Test client name helper"""
    strategy = OutlookStrategy()
    assert strategy.get_client_name() == "Outlook"
    print("✅ Outlook client name test passed")


def run_all_tests():
    """Run all Outlook strategy tests"""
    print("\n" + "=" * 60)
    print("Outlook ActiveSync Strategy Tests")
    print("=" * 60 + "\n")

    tests = [
        test_outlook_needs_empty_initial,
        test_outlook_window_size,
        test_outlook_truncation_honors_client,
        test_outlook_truncation_caps_mime,
        test_outlook_body_preference_order,
        test_outlook_pending_confirmation,
        test_outlook_client_name,
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
