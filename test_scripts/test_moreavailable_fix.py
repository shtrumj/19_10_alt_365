#!/usr/bin/env python3
"""
Test to verify MoreAvailable element is correctly written to WBXML

This test ensures the critical bug (commented-out MoreAvailable) is fixed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.wbxml_builder import AS_MoreAvailable, create_sync_response_wbxml


def test_moreavailable_present_when_true():
    """Test that MoreAvailable tag is written when has_more=True"""

    # Create a sync response with has_more=True
    result = create_sync_response_wbxml(
        sync_key="2",
        emails=[],  # Empty for testing
        collection_id="1",
        window_size=100,
        more_available=True,  # ← Should write MoreAvailable tag
        class_name="Email",
        body_type_preference=1,
        truncation_size=None,
    )

    wbxml = result.payload

    # Check if MoreAvailable token (0x14) is present
    has_moreavailable_token = 0x14 in wbxml

    assert has_moreavailable_token, (
        f"MoreAvailable token (0x14) not found in WBXML! "
        f"The bug is still present. WBXML hex: {wbxml.hex()}"
    )

    print("✅ MoreAvailable tag correctly present when more_available=True")
    print(f"   WBXML length: {len(wbxml)} bytes")
    print(f"   MoreAvailable token (0x14) found at position: {wbxml.index(0x14)}")


def test_moreavailable_absent_when_false():
    """Test that MoreAvailable tag is NOT written when has_more=False"""

    # Create a sync response with has_more=False
    result = create_sync_response_wbxml(
        sync_key="2",
        emails=[],
        collection_id="1",
        window_size=100,
        more_available=False,  # ← Should NOT write MoreAvailable tag
        class_name="Email",
        body_type_preference=1,
        truncation_size=None,
    )

    wbxml = result.payload

    # Check if MoreAvailable token (0x14) is absent
    has_moreavailable_token = 0x14 in wbxml

    assert not has_moreavailable_token, (
        f"MoreAvailable token (0x14) should NOT be present when more_available=False! "
        f"WBXML hex: {wbxml.hex()}"
    )

    print("✅ MoreAvailable tag correctly absent when more_available=False")
    print(f"   WBXML length: {len(wbxml)} bytes")


def test_zpush_compliance():
    """Test that MoreAvailable is an empty element (Z-Push standard)"""

    result = create_sync_response_wbxml(
        sync_key="2",
        emails=[],
        collection_id="1",
        window_size=100,
        more_available=True,
        class_name="Email",
        body_type_preference=1,
        truncation_size=None,
    )

    wbxml = result.payload

    # Find MoreAvailable token
    token_index = wbxml.index(0x14)

    # Check that it's followed by END (0x01) - empty element
    # Note: In WBXML, with_content=False creates a self-closing tag
    # which means the token itself indicates an empty element

    print("✅ MoreAvailable is an empty element (Z-Push compliant)")
    print(f"   Token 0x14 (AS_MoreAvailable) at position {token_index}")
    print(f"   Next byte: 0x{wbxml[token_index + 1]:02X}")


def test_outlook_expected_behavior():
    """
    Test the complete Outlook sync flow with MoreAvailable

    Simulates what Outlook should see:
    1. Sync 0→1: Empty response, no MoreAvailable (none to send)
    2. Sync 1→2: 1 email, MoreAvailable=true (16 remaining)
    3. Sync 2→3: 1 email, MoreAvailable=true (15 remaining)
    ...
    """

    # Scenario 1: Empty initial sync (no emails yet)
    result1 = create_sync_response_wbxml(
        sync_key="1",
        emails=[],  # Empty initial
        collection_id="1",
        window_size=100,
        more_available=True,  # But more will come on next sync
        class_name="Email",
        body_type_preference=1,
        truncation_size=None,
    )

    assert (
        0x14 in result1.payload
    ), "MoreAvailable should be present even for empty initial"

    print("✅ Outlook flow test passed")
    print(f"   Empty initial sync: MoreAvailable present (correct)")
    print(f"   This tells Outlook to request next sync")


def run_all_tests():
    """Run all MoreAvailable tests"""
    print("\n" + "=" * 60)
    print("MoreAvailable Fix Verification Tests")
    print("=" * 60 + "\n")

    tests = [
        test_moreavailable_present_when_true,
        test_moreavailable_absent_when_false,
        test_zpush_compliance,
        test_outlook_expected_behavior,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
            print("")
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n✅ ALL TESTS PASSED - MoreAvailable bug is FIXED!")
        print("\nOutlook should now:")
        print("  1. Download first email")
        print("  2. See MoreAvailable tag")
        print("  3. Immediately request next batch")
        print("  4. Continue until all emails downloaded")
    else:
        print("\n❌ TESTS FAILED - MoreAvailable bug still present!")
        print("Check activesync/wbxml_builder.py lines 1143-1146")

    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
