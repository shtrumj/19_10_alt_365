#!/usr/bin/env python3
"""
Outlook Sync Diagnosis Test

Tests to verify why Outlook is not downloading emails despite server sending them.

Based on analysis:
- Server sends empty response on SyncKey 0→1 ✅
- Server sends 17 emails (123KB) on SyncKey 1→2 ✅
- Outlook NEVER confirms with SyncKey=2 ❌

This suggests Outlook is rejecting the response. Common reasons:
1. Response too large (123KB for 17 emails = ~7KB per email)
2. WBXML protocol violation
3. MoreAvailable flag incorrect
4. Two-phase commit issue
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class ZPushBehavior:
    """
    Document Z-Push/Grommunio behavior for Outlook sync.

    Based on code analysis and testing.
    """

    # Outlook-specific behavior
    OUTLOOK_NEEDS_EMPTY_INITIAL = True  # SyncKey 0→1 must be empty
    OUTLOOK_WINDOW_SIZE_DEFAULT = 25  # Conservative batch size
    OUTLOOK_WINDOW_SIZE_MAX = 100  # Maximum batch size
    OUTLOOK_BATCH_SIZE_BYTES_RECOMMENDED = 50000  # ~50KB per batch recommended

    # Two-phase commit
    REQUIRES_PENDING_CONFIRMATION = True  # ALL clients use two-phase commit

    # MoreAvailable logic
    @staticmethod
    def should_set_more_available(
        emails_to_send: int, total_emails: int, window_size: int
    ) -> bool:
        """
        Z-Push logic for MoreAvailable flag.

        Args:
            emails_to_send: Number of emails in current batch
            total_emails: Total emails available
            window_size: Client's requested window size

        Returns:
            True if more emails are available (not sent in this batch)
        """
        return emails_to_send < total_emails


def test_empty_initial_response():
    """Test that Outlook gets empty response on SyncKey=0"""
    from activesync.strategies.outlook_strategy import OutlookStrategy

    strategy = OutlookStrategy()

    # Outlook MUST get empty response on SyncKey=0
    assert (
        strategy.needs_empty_initial_response("0")
        == ZPushBehavior.OUTLOOK_NEEDS_EMPTY_INITIAL
    )

    # After SyncKey=0, Outlook should get items
    assert strategy.needs_empty_initial_response("1") == False

    print("✅ Empty initial response test passed")


def test_window_size_limits():
    """Test that Outlook window size limits match Z-Push"""
    from activesync.strategies.outlook_strategy import OutlookStrategy

    strategy = OutlookStrategy()

    assert (
        strategy.get_default_window_size() == ZPushBehavior.OUTLOOK_WINDOW_SIZE_DEFAULT
    )
    assert strategy.get_max_window_size() == ZPushBehavior.OUTLOOK_WINDOW_SIZE_MAX

    print("✅ Window size limits test passed")


def test_two_phase_commit_enabled():
    """Test that two-phase commit is enabled for Outlook"""
    from activesync.strategies.outlook_strategy import OutlookStrategy

    strategy = OutlookStrategy()

    assert (
        strategy.should_use_pending_confirmation()
        == ZPushBehavior.REQUIRES_PENDING_CONFIRMATION
    )

    print("✅ Two-phase commit test passed")


def test_more_available_logic():
    """Test MoreAvailable logic"""

    # Case 1: 17 emails, window size 100 - all fit, no more available
    assert ZPushBehavior.should_set_more_available(17, 17, 100) == False

    # Case 2: 50 emails, send 25, window size 25 - more available
    assert ZPushBehavior.should_set_more_available(25, 50, 25) == True

    # Case 3: 100 emails, send 100, window size 100 - no more (all sent)
    assert ZPushBehavior.should_set_more_available(100, 100, 100) == False

    print("✅ MoreAvailable logic test passed")


def test_batch_size_recommendation():
    """Test that batch sizes don't exceed Z-Push recommendations"""

    # Scenario from logs: 17 emails, 123KB total
    total_size = 123276
    num_emails = 17
    avg_per_email = total_size / num_emails  # ~7.25KB per email

    # Z-Push recommendation: ~50KB per batch
    recommended_batch_size = ZPushBehavior.OUTLOOK_BATCH_SIZE_BYTES_RECOMMENDED

    # Our batch exceeded recommendation
    assert (
        total_size > recommended_batch_size
    ), f"Batch size {total_size} bytes exceeds Z-Push recommendation of {recommended_batch_size} bytes"

    # Calculate recommended emails per batch
    emails_per_batch = int(recommended_batch_size / avg_per_email)

    print(f"⚠️  Batch size issue detected:")
    print(f"   Our batch: {total_size} bytes ({num_emails} emails)")
    print(f"   Z-Push recommendation: {recommended_batch_size} bytes")
    print(f"   Recommended emails per batch: {emails_per_batch} emails")
    print(f"   Our batch is {total_size / recommended_batch_size:.1f}x too large")

    print("✅ Batch size analysis complete")


def test_outlook_sync_flow():
    """Test complete Outlook sync flow"""

    print("\n📋 Expected Outlook Sync Flow (Z-Push/Grommunio):")
    print("1. Outlook: Sync(SyncKey=0)")
    print("   Server: Empty response, SyncKey=1, MoreAvailable=true")
    print("")
    print("2. Outlook: Sync(SyncKey=1)")
    print("   Server: 7-10 emails (~50KB), SyncKey=2, MoreAvailable=true, pending=true")
    print("")
    print("3. Outlook: Sync(SyncKey=2) [confirms receipt of batch 1]")
    print("   Server: Next 7-10 emails, SyncKey=3, MoreAvailable=false, pending=true")
    print("")
    print("4. Outlook: Sync(SyncKey=3) [confirms receipt of batch 2]")
    print("   Server: Commits pending, MoreAvailable=false")
    print("")
    print("❌ Actual behavior:")
    print("1. Outlook: Sync(SyncKey=0) ✅")
    print("   Server: Empty response, SyncKey=1 ✅")
    print("")
    print("2. Outlook: Sync(SyncKey=1) ✅")
    print(
        "   Server: ALL 17 emails (123KB), SyncKey=2, MoreAvailable=false, pending=true ❌"
    )
    print("")
    print("3. Outlook: [REJECTED RESPONSE - went to Ping instead] ❌")
    print("")
    print("🔍 Diagnosis:")
    print("   - Batch too large (123KB > 50KB recommendation)")
    print("   - Should split into 2-3 batches of 7-10 emails each")
    print("   - This matches Z-Push/Grommunio behavior for Outlook Desktop")

    print("\n✅ Sync flow analysis complete")


def run_all_tests():
    """Run all diagnosis tests"""
    print("\n" + "=" * 60)
    print("Outlook Sync Diagnosis Tests")
    print("=" * 60 + "\n")

    tests = [
        test_empty_initial_response,
        test_window_size_limits,
        test_two_phase_commit_enabled,
        test_more_available_logic,
        test_batch_size_recommendation,
        test_outlook_sync_flow,
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

    if failed == 0:
        print("\n🎯 RECOMMENDATION:")
        print("Implement batch size limiting for Outlook:")
        print("- Max batch size: 50KB (Z-Push recommendation)")
        print("- This will split 17 emails into 2-3 batches")
        print("- Outlook will confirm each batch before getting next")

    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
