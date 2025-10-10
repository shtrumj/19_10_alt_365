#!/usr/bin/env python3
"""
Z-Push/Grommunio Comparison Tests

Side-by-side comparison of our ActiveSync implementation with Z-Push and Grommunio
expected behavior. This ensures our implementation is compliant with industry standards.

References:
- Z-Push: https://github.com/Z-Hub/Z-Push
- Grommunio-sync: https://github.com/grommunio/grommunio-sync
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.strategies.ios_strategy import IOSStrategy
from activesync.strategies.outlook_strategy import OutlookStrategy


class ZPushExpectedBehavior:
    """
    Document Z-Push behavior from source code analysis.

    Based on Z-Push 2.6.x and Grommunio-sync implementations.
    """

    # Empty initial response requirements
    OUTLOOK_INITIAL_SYNC_EMPTY = True  # Outlook gets empty on 0→1
    IOS_INITIAL_SYNC_EMPTY = False  # iOS gets items on 0→1

    # Window size limits
    MAX_WINDOW_SIZE = 100  # Z-Push default maximum
    OUTLOOK_DEFAULT_WINDOW_SIZE = 25  # Conservative for Outlook
    IOS_DEFAULT_WINDOW_SIZE = 50  # More aggressive for iOS

    # MIME size limits
    MIME_MAX_SIZE = 512000  # 500KB (512000 bytes)

    # Two-phase commit
    REQUIRES_PENDING_CONFIRMATION = True  # All clients use two-phase commit

    @staticmethod
    def get_truncation_for_type(body_type: int, client_request: int = None) -> int:
        """
        Z-Push truncation logic.

        Args:
            body_type: 1=plain, 2=HTML, 4=MIME
            client_request: Client's requested truncation size

        Returns:
            Effective truncation size
        """
        if body_type == 4:  # MIME
            # Cap at 512KB
            if client_request is None:
                return 512000
            return min(client_request, 512000)
        else:  # Type 1 or 2 (plain text or HTML)
            # Honor client's request exactly - no override!
            return client_request


def test_our_outlook_empty_response_matches_zpush():
    """Test that our Outlook empty response behavior matches Z-Push"""
    our_strategy = OutlookStrategy()

    # Test empty response on SyncKey=0
    our_empty = our_strategy.needs_empty_initial_response("0")
    zpush_empty = ZPushExpectedBehavior.OUTLOOK_INITIAL_SYNC_EMPTY

    assert (
        our_empty == zpush_empty
    ), f"Outlook empty initial response mismatch: ours={our_empty}, Z-Push={zpush_empty}"

    print("✅ Outlook empty initial response matches Z-Push")


def test_our_ios_immediate_items_matches_zpush():
    """Test that our iOS immediate item delivery matches Z-Push"""
    our_strategy = IOSStrategy()

    # Test that iOS gets items immediately
    our_empty = our_strategy.needs_empty_initial_response("0")
    zpush_empty = ZPushExpectedBehavior.IOS_INITIAL_SYNC_EMPTY

    assert (
        our_empty == zpush_empty
    ), f"iOS empty initial response mismatch: ours={our_empty}, Z-Push={zpush_empty}"

    print("✅ iOS immediate item delivery matches Z-Push")


def test_our_outlook_window_size_matches_zpush():
    """Test that our Outlook window sizes match Z-Push"""
    our_strategy = OutlookStrategy()

    # Test maximum window size
    assert our_strategy.get_max_window_size() == ZPushExpectedBehavior.MAX_WINDOW_SIZE

    # Test default window size
    assert (
        our_strategy.get_default_window_size()
        == ZPushExpectedBehavior.OUTLOOK_DEFAULT_WINDOW_SIZE
    )

    print("✅ Outlook window sizes match Z-Push")


def test_our_ios_window_size_matches_zpush():
    """Test that our iOS window sizes match Z-Push"""
    our_strategy = IOSStrategy()

    # Test maximum window size
    assert our_strategy.get_max_window_size() == ZPushExpectedBehavior.MAX_WINDOW_SIZE

    # Test default window size
    assert (
        our_strategy.get_default_window_size()
        == ZPushExpectedBehavior.IOS_DEFAULT_WINDOW_SIZE
    )

    print("✅ iOS window sizes match Z-Push")


def test_outlook_type1_truncation_matches_zpush():
    """Test Outlook Type=1 (plain text) truncation matches Z-Push"""
    our_strategy = OutlookStrategy()

    # Test with 32KB request (typical iPhone, but testing Outlook strategy)
    our_trunc = our_strategy.get_truncation_strategy(1, 32768, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(1, 32768)

    assert (
        our_trunc == zpush_trunc
    ), f"Type=1 truncation mismatch: ours={our_trunc}, Z-Push={zpush_trunc}"

    # Test with 10KB request
    our_trunc = our_strategy.get_truncation_strategy(1, 10240, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(1, 10240)

    assert our_trunc == zpush_trunc

    print("✅ Outlook Type=1 truncation matches Z-Push")


def test_outlook_type2_truncation_matches_zpush():
    """Test Outlook Type=2 (HTML) truncation matches Z-Push"""
    our_strategy = OutlookStrategy()

    # Test with 32KB request
    our_trunc = our_strategy.get_truncation_strategy(2, 32768, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(2, 32768)

    assert our_trunc == zpush_trunc

    print("✅ Outlook Type=2 truncation matches Z-Push")


def test_outlook_type4_truncation_matches_zpush():
    """Test Outlook Type=4 (MIME) truncation matches Z-Push"""
    our_strategy = OutlookStrategy()

    # Test with 1MB request (should cap at 512KB)
    our_trunc = our_strategy.get_truncation_strategy(4, 1000000, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(4, 1000000)

    assert (
        our_trunc == zpush_trunc == 512000
    ), f"Type=4 truncation mismatch: ours={our_trunc}, Z-Push={zpush_trunc}"

    # Test with 100KB request (should not cap)
    our_trunc = our_strategy.get_truncation_strategy(4, 100000, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(4, 100000)

    assert our_trunc == zpush_trunc == 100000

    # Test with None (unlimited) request (should cap at 512KB)
    our_trunc = our_strategy.get_truncation_strategy(4, None, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(4, None)

    assert our_trunc == zpush_trunc == 512000

    print("✅ Outlook Type=4 MIME truncation matches Z-Push")


def test_ios_truncation_matches_zpush():
    """Test iOS truncation strategy matches Z-Push"""
    our_strategy = IOSStrategy()

    # iOS typically requests 32KB for text
    our_trunc = our_strategy.get_truncation_strategy(1, 32768, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(1, 32768)
    assert our_trunc == zpush_trunc

    # iOS MIME should also cap at 512KB
    our_trunc = our_strategy.get_truncation_strategy(4, 1000000, False)
    zpush_trunc = ZPushExpectedBehavior.get_truncation_for_type(4, 1000000)
    assert our_trunc == zpush_trunc == 512000

    print("✅ iOS truncation matches Z-Push")


def test_two_phase_commit_matches_zpush():
    """Test that two-phase commit requirement matches Z-Push"""
    outlook_strategy = OutlookStrategy()
    ios_strategy = IOSStrategy()

    # Z-Push requires two-phase commit for all clients
    assert (
        outlook_strategy.should_use_pending_confirmation()
        == ZPushExpectedBehavior.REQUIRES_PENDING_CONFIRMATION
    )
    assert (
        ios_strategy.should_use_pending_confirmation()
        == ZPushExpectedBehavior.REQUIRES_PENDING_CONFIRMATION
    )

    print("✅ Two-phase commit requirement matches Z-Push")


def run_all_tests():
    """Run all Z-Push comparison tests"""
    print("\n" + "=" * 60)
    print("Z-Push/Grommunio Comparison Tests")
    print("=" * 60 + "\n")

    tests = [
        test_our_outlook_empty_response_matches_zpush,
        test_our_ios_immediate_items_matches_zpush,
        test_our_outlook_window_size_matches_zpush,
        test_our_ios_window_size_matches_zpush,
        test_outlook_type1_truncation_matches_zpush,
        test_outlook_type2_truncation_matches_zpush,
        test_outlook_type4_truncation_matches_zpush,
        test_ios_truncation_matches_zpush,
        test_two_phase_commit_matches_zpush,
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
    if passed == len(tests):
        print("🎉 100% Z-Push/Grommunio compliance achieved!")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
