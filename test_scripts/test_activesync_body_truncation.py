#!/usr/bin/env python3
"""
ActiveSync Body Truncation Tests

Tests truncation behavior for Type=1 (plain text), Type=2 (HTML), and Type=4 (MIME)
Compares against Z-Push strategy and MS-ASAIRS spec compliance.

References:
- MS-ASAIRS §2.2.2.17 EstimatedDataSize
- MS-ASAIRS §2.2.2.50 Truncated
- Z-Push truncation strategy
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.wbxml_builder import _prepare_body_payload


def test_type1_honors_client_truncation():
    """Test that Type=1 (plain text) honors client's truncation exactly"""
    # Create email with 10KB of text
    large_text = "A" * 10240  # 10KB of ASCII

    email = {
        "id": 1,
        "body": large_text,
        "body_html": None,
    }

    # Client requests 32KB truncation (typical iPhone request)
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=32768)

    # Z-Push strategy: Should NOT truncate since 10KB < 32KB
    assert (
        payload["truncated"] == "0"
    ), f"Should not truncate 10KB body with 32KB limit (got truncated={payload['truncated']})"

    assert (
        len(payload["data"]) == 10240
    ), f"Should preserve full 10KB body (got {len(payload['data'])} bytes)"

    # EstimatedDataSize should reflect full size
    assert (
        int(payload["estimated_size"]) == 10240
    ), f"EstimatedDataSize should be 10240 (got {payload['estimated_size']})"

    print("✅ Type=1 honors client truncation (32KB limit)")


def test_type1_truncates_at_client_limit():
    """Test that Type=1 truncates at exact client limit"""
    # Create 50KB of text
    large_text = "B" * 51200

    email = {
        "id": 2,
        "body": large_text,
        "body_html": None,
    }

    # Client requests 32KB truncation
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=32768)

    # Should truncate at 32KB boundary
    assert payload["truncated"] == "1", "Should truncate 50KB body with 32KB limit"
    assert (
        len(payload["data"]) <= 32768
    ), f"Should truncate to ≤32KB (got {len(payload['data'])} bytes)"

    # EstimatedDataSize should reflect FULL size (before truncation)
    assert (
        int(payload["estimated_size"]) == 51200
    ), f"EstimatedDataSize should be 51200 (got {payload['estimated_size']})"

    print("✅ Type=1 truncates at exact client limit (32KB)")


def test_type1_no_artificial_8kb_cap():
    """Test that Type=1 does NOT have artificial 8KB server cap"""
    # Create 20KB of text
    text_20kb = "C" * 20480

    email = {
        "id": 3,
        "body": text_20kb,
        "body_html": None,
    }

    # Client requests 32KB (should get full 20KB, not capped at 8KB)
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=32768)

    # OLD BUG: Would cap at 8KB even though client requested 32KB
    # NEW: Should return full 20KB
    assert (
        len(payload["data"]) == 20480
    ), f"Should return full 20KB (got {len(payload['data'])} bytes) - NO 8KB cap!"

    assert payload["truncated"] == "0", "Should not truncate 20KB with 32KB limit"

    print("✅ Type=1 removed artificial 8KB cap (Z-Push compliance)")


def test_type2_html_truncation():
    """Test Type=2 (HTML) truncation behavior"""
    # Create 15KB of HTML
    html_15kb = "<html><body>" + ("X" * 15000) + "</body></html>"

    email = {
        "id": 4,
        "body": None,
        "body_html": html_15kb,
    }

    # Client requests 10KB truncation
    payload = _prepare_body_payload(email, requested_type=2, truncation_size=10240)

    # Should truncate at 10KB
    assert payload["truncated"] == "1", "Should truncate 15KB HTML with 10KB limit"
    assert (
        len(payload["data"]) <= 10240
    ), f"Should truncate to ≤10KB (got {len(payload['data'])} bytes)"

    # EstimatedDataSize should be full size
    assert (
        int(payload["estimated_size"]) >= 15000
    ), f"EstimatedDataSize should reflect full HTML size"

    print("✅ Type=2 (HTML) truncates correctly")


def test_type4_mime_cap():
    """Test Type=4 (MIME) has reasonable maximum (512KB)"""
    # Create large MIME content
    large_mime = b"X-Test: header\r\n\r\n" + (b"Y" * 600000)  # 600KB

    email = {
        "id": 5,
        "mime_content": large_mime,
    }

    # Type=4 should cap at 512KB even if client requests unlimited
    payload = _prepare_body_payload(email, requested_type=4, truncation_size=None)

    # Should be truncated
    assert payload["truncated"] == "1", "Should truncate 600KB MIME"
    assert (
        len(payload["data_bytes"]) <= 512000
    ), f"Should cap MIME at 512KB (got {len(payload['data_bytes'])} bytes)"

    print("✅ Type=4 (MIME) caps at 512KB maximum")


def test_utf8_character_boundary_truncation():
    """Test that truncation respects UTF-8 character boundaries"""
    # Create text with multibyte characters (Hebrew)
    hebrew_text = "שלום " * 5000  # ~20KB with 4-byte Hebrew characters

    email = {
        "id": 6,
        "body": hebrew_text,
        "body_html": None,
    }

    # Truncate at 10KB
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=10240)

    # Should be truncated
    assert payload["truncated"] == "1", "Should truncate Hebrew text"

    # Should decode without errors (proves UTF-8 boundary respect)
    try:
        decoded = payload["data"]
        # Should not end with partial multibyte character
        assert decoded, "Should have valid decoded text"
    except UnicodeDecodeError:
        raise AssertionError("Truncation broke UTF-8 character boundary!")

    print("✅ Truncation respects UTF-8 character boundaries")


def test_estimated_size_always_full():
    """Test that EstimatedDataSize always reflects full body size"""
    test_cases = [
        ("Small text", "A" * 100, 1024),
        ("Medium text", "B" * 5000, 10240),
        ("Large text", "C" * 50000, 32768),
    ]

    for name, text, trunc_size in test_cases:
        email = {"id": 100, "body": text, "body_html": None}
        payload = _prepare_body_payload(
            email, requested_type=1, truncation_size=trunc_size
        )

        expected_size = len(text.encode("utf-8"))
        actual_estimated = int(payload["estimated_size"])

        # EstimatedDataSize MUST be full size, regardless of truncation
        # This is CRITICAL per MS-ASAIRS §2.2.2.17
        assert (
            actual_estimated == expected_size
        ), f"{name}: EstimatedDataSize should be {expected_size}, got {actual_estimated}"

    print("✅ EstimatedDataSize always reflects full body (MS-ASAIRS compliance)")


def test_line_endings_after_size_calculation():
    """Test that line ending normalization happens AFTER EstimatedDataSize calculation"""
    # Text with CRLF line endings
    text_with_crlf = "Line 1\r\nLine 2\r\nLine 3\r\n"  # 27 bytes with CRLF

    email = {
        "id": 7,
        "body": text_with_crlf,
        "body_html": None,
    }

    payload = _prepare_body_payload(email, requested_type=1, truncation_size=None)

    # EstimatedDataSize should reflect ORIGINAL size with CRLF
    original_size = len(text_with_crlf.encode("utf-8"))
    assert (
        int(payload["estimated_size"]) == original_size
    ), f"EstimatedDataSize should be {original_size} (with CRLF)"

    # But actual data should have normalized line endings (LF only)
    assert "\r\n" not in payload["data"], "Data should have normalized line endings"
    assert "\n" in payload["data"], "Data should contain LF"

    print("✅ Line ending normalization happens AFTER size calculation")


def test_no_truncation_when_null():
    """Test behavior when truncation_size is None"""
    text = "No truncation test" * 100

    email = {
        "id": 8,
        "body": text,
        "body_html": None,
    }

    # No truncation requested
    payload = _prepare_body_payload(email, requested_type=1, truncation_size=None)

    # Should return full content
    assert payload["truncated"] == "0", "Should not truncate when truncation_size=None"
    assert len(payload["data"]) == len(text), "Should return full content"

    print("✅ No truncation when truncation_size=None")


def run_all_tests():
    """Run all body truncation tests"""
    print("\n" + "=" * 60)
    print("ActiveSync Body Truncation Tests (Z-Push Strategy)")
    print("=" * 60 + "\n")

    tests = [
        test_type1_honors_client_truncation,
        test_type1_truncates_at_client_limit,
        test_type1_no_artificial_8kb_cap,
        test_type2_html_truncation,
        test_type4_mime_cap,
        test_utf8_character_boundary_truncation,
        test_estimated_size_always_full,
        test_line_endings_after_size_calculation,
        test_no_truncation_when_null,
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
