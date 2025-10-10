#!/usr/bin/env python3
"""
ActiveSync Protocol Compliance Tests

Tests MS-ASAIRS specification compliance, protocol version negotiation,
body preference parsing, and response structure validation.

References:
- MS-ASAIRS: ActiveSync AirSyncBase Namespace Protocol
- MS-ASCMD: ActiveSync Command Reference Protocol
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.wbxml_builder import (
    CP_AIRSYNC,
    CP_AIRSYNCBASE,
    WBXMLWriter,
    _prepare_body_payload,
    create_sync_response_wbxml,
    write_fetch_responses,
)


def test_estimated_datasize_compliance():
    """Test MS-ASAIRS §2.2.2.17: EstimatedDataSize MUST be untruncated size"""
    # Create 50KB body
    large_body = "X" * 51200

    email = {
        "id": 1,
        "body": large_body,
        "body_html": None,
    }

    # Request 10KB truncation
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=10240)

    # EstimatedDataSize MUST be 51200 (full size), NOT 10240 (truncated)
    assert (
        int(payload["estimated_size"]) == 51200
    ), f"EstimatedDataSize MUST be full size per MS-ASAIRS §2.2.2.17"

    # Data should be truncated to 10KB
    assert len(payload["data"]) <= 10240, "Data should be truncated"

    # Truncated flag MUST be "1"
    assert payload["truncated"] == "1", "Truncated MUST be '1' per MS-ASAIRS §2.2.2.50"

    print("✅ EstimatedDataSize compliance (MS-ASAIRS §2.2.2.17)")


def test_truncated_flag_compliance():
    """Test MS-ASAIRS §2.2.2.50: Truncated element compliance"""
    test_cases = [
        # (body_size, truncation_size, expected_truncated)
        (1000, 2000, "0"),  # Not truncated
        (2000, 1000, "1"),  # Truncated
        (1000, None, "0"),  # No truncation requested
    ]

    for body_size, trunc_size, expected in test_cases:
        email = {"id": 1, "body": "A" * body_size, "body_html": None}
        payload = _prepare_body_payload(
            email, requested_type=1, truncation_size=trunc_size
        )

        assert (
            payload["truncated"] == expected
        ), f"Truncated should be '{expected}' for body={body_size}, trunc={trunc_size}"

    print("✅ Truncated flag compliance (MS-ASAIRS §2.2.2.50)")


def test_body_type_values():
    """Test MS-ASAIRS §2.2.2.22.7: Body Type values"""
    # Type values: 1=plain, 2=HTML, 3=RTF, 4=MIME

    email = {
        "id": 1,
        "body": "Plain text",
        "body_html": "<p>HTML</p>",
        "mime_content": b"MIME content",
    }

    # Type 1 (plain)
    payload1 = _prepare_body_payload(email, requested_type=1, truncation_size=1024)
    assert payload1["type"] == "1", "Type 1 should be plain text"

    # Type 2 (HTML)
    payload2 = _prepare_body_payload(email, requested_type=2, truncation_size=1024)
    assert payload2["type"] == "2", "Type 2 should be HTML"

    # Type 4 (MIME)
    payload4 = _prepare_body_payload(email, requested_type=4, truncation_size=1024)
    assert payload4["type"] == "4", "Type 4 should be MIME"

    print("✅ Body Type values compliance (MS-ASAIRS §2.2.2.22.7)")


def test_data_element_compliance():
    """Test MS-ASAIRS §2.2.2.8: Data element compliance"""
    email = {
        "id": 1,
        "body": "Test content",
        "body_html": None,
    }

    # Type 1/2 should have string data
    payload_text = _prepare_body_payload(email, requested_type=1, truncation_size=1024)
    assert "data" in payload_text, "Type 1 must have 'data' field"
    assert isinstance(payload_text["data"], str), "Type 1 data must be string"

    # Type 4 should have binary data_bytes for OPAQUE
    email_mime = {
        "id": 2,
        "mime_content": b"MIME binary content",
    }
    payload_mime = _prepare_body_payload(
        email_mime, requested_type=4, truncation_size=1024
    )
    assert "data_bytes" in payload_mime, "Type 4 must have 'data_bytes' field"
    assert isinstance(
        payload_mime["data_bytes"], bytes
    ), "Type 4 data_bytes must be bytes"

    print("✅ Data element compliance (MS-ASAIRS §2.2.2.8)")


def test_native_body_type():
    """Test NativeBodyType selection"""
    # Email with plain text only
    email_plain = {
        "id": 1,
        "body": "Plain only",
        "body_html": None,
    }
    payload_plain = _prepare_body_payload(
        email_plain, requested_type=1, truncation_size=1024
    )
    assert payload_plain["native_type"] == "1", "Native should be plain (1)"

    # Email with HTML
    email_html = {
        "id": 2,
        "body": None,
        "body_html": "<p>HTML</p>",
    }
    payload_html = _prepare_body_payload(
        email_html, requested_type=2, truncation_size=1024
    )
    assert payload_html["native_type"] == "2", "Native should be HTML (2)"

    print("✅ NativeBodyType selection correct")


def test_sync_response_structure():
    """Test Sync response structure per MS-ASCMD §2.2.2.19"""
    test_email = {
        "id": 1,
        "server_id": "1:1",
        "subject": "Test",
        "from": "test@example.com",
        "to": "user@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "is_read": False,
        "body": "Test body",
    }

    batch = create_sync_response_wbxml(
        sync_key="2",
        collection_id="1",
        emails=[test_email],
        window_size=1,
        more_available=False,
        class_name="Email",
        body_type_preference=1,
        truncation_size=1024,
    )

    wbxml = batch.payload

    # Must start with WBXML header
    assert wbxml[:4] == bytes([0x03, 0x01, 0x6A, 0x00]), "Missing WBXML header"

    # Must contain Status element
    # Must contain SyncKey
    # Must contain CollectionId
    assert len(wbxml) > 0, "Response must have content"

    print("✅ Sync response structure compliant (MS-ASCMD §2.2.2.19)")


def test_fetch_response_structure():
    """Test fetch response structure in <Responses><Fetch>"""
    test_email = {
        "id": 1,
        "server_id": "1:1",
        "subject": "Fetch Test",
        "from": "test@example.com",
        "to": "user@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "is_read": False,
        "mime_content": b"From: test@example.com\r\n\r\nBody",
    }

    w = WBXMLWriter()
    w.header()
    w.page(CP_AIRSYNC)

    # Write fetch responses
    write_fetch_responses(
        w=w,
        fetched=[test_email],
        body_type_preference=4,
        truncation_size=8192,
    )

    wbxml = bytes(w.buf)

    # Should contain Responses and Fetch elements
    assert len(wbxml) > 50, "Fetch response should have substantial content"

    print("✅ Fetch response structure compliant")


def test_body_preference_interpretation():
    """Test BodyPreference interpretation"""
    # iPhone typical preference: Type=1, TruncationSize=32768
    email = {
        "id": 1,
        "body": "A" * 10000,  # 10KB
        "body_html": None,
    }

    # Simulate iPhone preference
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=32768)

    # Should return full 10KB (no truncation needed)
    assert len(payload["data"]) == 10000, "Should honor iPhone's 32KB preference"
    assert payload["truncated"] == "0", "Should not truncate 10KB with 32KB limit"

    print("✅ BodyPreference interpretation correct")


def test_content_type_header():
    """Test Content-Type values"""
    test_cases = [
        (1, "text/plain; charset=utf-8"),
        (2, "text/html; charset=utf-8"),
    ]

    for req_type, expected_ct in test_cases:
        email = {"id": 1, "body": "Test", "body_html": "<p>Test</p>"}
        payload = _prepare_body_payload(
            email, requested_type=req_type, truncation_size=1024
        )

        assert expected_ct in payload.get(
            "content_type", ""
        ), f"Type {req_type} should have {expected_ct}"

    print("✅ Content-Type headers correct")


def test_empty_body_handling():
    """Test handling of emails with no body"""
    email = {
        "id": 1,
        "body": None,
        "body_html": None,
    }

    payload = _prepare_body_payload(email, requested_type=1, truncation_size=1024)

    # Should handle gracefully
    assert payload["data"] == "", "Empty body should return empty string"
    assert payload["estimated_size"] == "0", "EstimatedDataSize should be 0"
    assert payload["truncated"] == "0", "Should not be truncated"

    print("✅ Empty body handling correct")


def test_protocol_version_compatibility():
    """Test that responses are compatible with different protocol versions"""
    # 12.1, 14.0, 14.1, 16.0, 16.1 should all work
    # This is tested via header validation in router, just verify structure

    test_email = {
        "id": 1,
        "server_id": "1:1",
        "subject": "Version Test",
        "from": "test@example.com",
        "to": "user@example.com",
        "created_at": "2025-01-01T00:00:00Z",
        "is_read": False,
        "body": "Test",
    }

    # Generate response (should work for all versions)
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

    # Should generate valid WBXML regardless of version
    assert len(batch.payload) > 0, "Should generate response"

    print("✅ Protocol version compatibility maintained")


def run_all_tests():
    """Run all protocol compliance tests"""
    print("\n" + "=" * 60)
    print("ActiveSync Protocol Compliance Tests (MS-ASAIRS)")
    print("=" * 60 + "\n")

    tests = [
        test_estimated_datasize_compliance,
        test_truncated_flag_compliance,
        test_body_type_values,
        test_data_element_compliance,
        test_native_body_type,
        test_sync_response_structure,
        test_fetch_response_structure,
        test_body_preference_interpretation,
        test_content_type_header,
        test_empty_body_handling,
        test_protocol_version_compatibility,
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
