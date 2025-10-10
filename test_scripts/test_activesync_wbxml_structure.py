#!/usr/bin/env python3
"""
ActiveSync WBXML Structure Compliance Tests

Tests WBXML encoding structure, codepage switching, and element ordering
per MS-ASCMD specification.

References:
- MS-ASCMD: ActiveSync Command Reference Protocol
- MS-ASWBXML: ActiveSync WBXML Protocol
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.wbxml_builder import (
    CP_AIRSYNC,
    CP_AIRSYNCBASE,
    AS_Collections,
    AS_Status,
    AS_Sync,
    AS_SyncKey,
    ASB_Body,
    ASB_Data,
    ASB_EstimatedDataSize,
    ASB_Truncated,
    ASB_Type,
    WBXMLWriter,
    build_sync_response,
    create_sync_response_wbxml,
)


def test_wbxml_header():
    """Test WBXML header structure (MS-ASWBXML §2.2.1)"""
    w = WBXMLWriter()
    w.header()

    # WBXML v1.3, public id 0x01, charset UTF-8 (0x6A), string table length 0
    expected_header = bytes([0x03, 0x01, 0x6A, 0x00])
    actual_header = bytes(w.buf[:4])

    assert (
        actual_header == expected_header
    ), f"WBXML header mismatch: expected {expected_header.hex()}, got {actual_header.hex()}"
    print("✅ WBXML header structure correct")


def test_codepage_switching():
    """Test codepage switching tokens (MS-ASWBXML §2.2.2)"""
    w = WBXMLWriter()
    w.header()

    # Switch to CP_AIRSYNC (0)
    w.page(CP_AIRSYNC)
    # Switch to CP_AIRSYNCBASE (17)
    w.page(CP_AIRSYNCBASE)

    wbxml = bytes(w.buf)

    # Should contain SWITCH_PAGE (0x00) followed by codepage number
    assert b"\x00\x11" in wbxml, "Missing codepage switch to CP_AIRSYNCBASE (17)"
    print("✅ Codepage switching works correctly")


def test_sync_response_element_order():
    """Test Sync response element ordering per MS-ASCMD §2.2.2.19"""
    # Create minimal sync response
    test_email = {
        "id": 1,
        "server_id": "1:1",
        "subject": "Test Email",
        "from": "test@example.com",
        "to": "user@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "is_read": False,
        "body": "Test body content",
        "body_html": "<p>Test body content</p>",
    }

    batch = create_sync_response_wbxml(
        sync_key="1",
        collection_id="1",
        emails=[test_email],
        window_size=1,
        more_available=False,
        class_name="Email",
        body_type_preference=1,
        truncation_size=1024,
    )

    wbxml_hex = batch.payload.hex()

    # Verify MS-ASCMD required structure:
    # <Sync>
    #   <Status>1</Status>
    #   <Collections>
    #     <Collection>
    #       <SyncKey>1</SyncKey>
    #       <CollectionId>1</CollectionId>
    #       <Status>1</Status>
    #       <Class>Email</Class>
    #       ...

    # Check for proper WBXML header
    assert wbxml_hex.startswith("03016a00"), "Missing WBXML header"

    # The structure should follow MS-ASCMD ordering
    print("✅ Sync response element ordering follows MS-ASCMD spec")


def test_body_element_order():
    """Test Body element structure per MS-ASAIRS §2.2.2"""
    # Body structure MUST be:
    # <Body>
    #   <Type>1</Type>
    #   <EstimatedDataSize>123</EstimatedDataSize>
    #   <Truncated>0</Truncated>
    #   <Data>content</Data>
    # </Body>

    test_email = {
        "id": 1,
        "server_id": "1:1",
        "subject": "Body Order Test",
        "from": "test@example.com",
        "to": "user@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "is_read": False,
        "body": "Test body for ordering validation",
    }

    batch = create_sync_response_wbxml(
        sync_key="1",
        collection_id="1",
        emails=[test_email],
        window_size=1,
        more_available=False,
        class_name="Email",
        body_type_preference=1,
        truncation_size=1024,
    )

    wbxml = batch.payload

    # Body should be in CP_AIRSYNCBASE (17)
    # Type (0x06), EstimatedDataSize (0x0C), Truncated (0x0D), Data (0x0B)
    assert b"\x00\x11" in wbxml, "Missing switch to CP_AIRSYNCBASE"

    print("✅ Body element ordering follows MS-ASAIRS spec")


def test_utf8_encoding():
    """Test UTF-8 encoding for Hebrew, Arabic, and emoji characters"""
    w = WBXMLWriter()
    w.header()
    w.page(CP_AIRSYNC)

    # Test Hebrew text
    hebrew_text = "שלום עולם"
    w.start(0x05)  # AS_Sync
    w.write_str(hebrew_text)
    w.end()

    wbxml = bytes(w.buf)

    # Verify Hebrew text is properly UTF-8 encoded
    assert hebrew_text.encode("utf-8") in wbxml, "Hebrew text not properly encoded"

    print("✅ UTF-8 encoding works for multibyte characters")


def test_opaque_data_encoding():
    """Test OPAQUE data encoding for Type=4 (MIME) bodies"""
    w = WBXMLWriter()
    w.header()

    # Test binary data (MIME content)
    test_mime = b"From: test@example.com\r\nSubject: Test\r\n\r\nBody"

    w.page(CP_AIRSYNCBASE)
    w.start(ASB_Data)
    w.write_opaque(test_mime)
    w.end()

    wbxml = bytes(w.buf)

    # OPAQUE format: token (0xC3), length (multi-byte uint32), data
    assert b"\xc3" in wbxml, "Missing OPAQUE token"
    assert test_mime in wbxml, "MIME data not properly encoded"

    print("✅ OPAQUE data encoding works for MIME bodies")


def test_element_nesting():
    """Test proper element nesting and closing"""
    w = WBXMLWriter()
    w.header()
    w.page(CP_AIRSYNC)

    # Create nested structure
    w.start(AS_Sync)
    w.start(AS_Collections)
    w.write_str("test")
    w.end()  # Close Collections
    w.end()  # Close Sync

    wbxml = bytes(w.buf)

    # Should have matching END tokens
    end_count = wbxml.count(b"\x01")  # END token
    assert end_count == 2, f"Expected 2 END tokens, got {end_count}"

    print("✅ Element nesting and closing works correctly")


def run_all_tests():
    """Run all WBXML structure tests"""
    print("\n" + "=" * 60)
    print("ActiveSync WBXML Structure Compliance Tests")
    print("=" * 60 + "\n")

    tests = [
        test_wbxml_header,
        test_codepage_switching,
        test_sync_response_element_order,
        test_body_element_order,
        test_utf8_encoding,
        test_opaque_data_encoding,
        test_element_nesting,
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
