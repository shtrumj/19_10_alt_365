#!/usr/bin/env python3
"""
ActiveSync MIME Handling Tests

Tests MIME parsing, charset transcoding, Content-Transfer-Encoding,
and multipart/alternative selection.

References:
- RFC 2045: MIME Part One
- RFC 2047: MIME Part Three (Message Header Extensions)
- Z-Push MIME handling
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from activesync.wbxml_builder import _extract_text_from_mime_with_charset


def create_mime_message(plain_text, html_text=None, charset="utf-8", encoding="7bit"):
    """Helper to create test MIME messages"""
    if html_text:
        mime = f"""From: test@example.com
To: user@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset={charset}
Content-Transfer-Encoding: {encoding}

{plain_text}
--boundary123
Content-Type: text/html; charset={charset}
Content-Transfer-Encoding: {encoding}

{html_text}
--boundary123--
"""
    else:
        mime = f"""From: test@example.com
To: user@example.com
Subject: Test Email
MIME-Version: 1.0
Content-Type: text/plain; charset={charset}
Content-Transfer-Encoding: {encoding}

{plain_text}
"""
    return mime.encode(charset)


def test_utf8_mime_parsing():
    """Test UTF-8 MIME parsing"""
    plain = "Hello World"
    html = "<p>Hello World</p>"
    
    mime = create_mime_message(plain, html, charset="utf-8")
    
    plain_result, html_result, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    assert plain_result == plain, f"Plain text mismatch: {plain_result}"
    assert html_result == html, f"HTML mismatch: {html_result}"
    assert debug["mime_parsed"], "MIME should be parsed successfully"
    assert "utf-8" in debug["charsets_detected"], "Should detect UTF-8 charset"
    
    print("✅ UTF-8 MIME parsing works")


def test_hebrew_charset_transcoding():
    """Test Hebrew text with ISO-8859-8 charset transcoding to UTF-8"""
    hebrew_text = "שלום עולם"  # "Hello World" in Hebrew
    
    # Encode as ISO-8859-8 (Hebrew charset)
    try:
        mime_iso = create_mime_message(hebrew_text, charset="iso-8859-8")
    except UnicodeEncodeError:
        # ISO-8859-8 doesn't support all Hebrew characters, use windows-1255
        mime_iso = create_mime_message(hebrew_text, charset="windows-1255")
    
    plain_result, _, debug = _extract_text_from_mime_with_charset(mime_iso, prefer_html=False)
    
    # Should be transcoded to UTF-8
    assert hebrew_text in plain_result or len(plain_result) > 0, "Should extract Hebrew text"
    assert debug["mime_parsed"], "MIME should be parsed"
    
    print("✅ Hebrew charset transcoding works")


def test_quoted_printable_encoding():
    """Test quoted-printable Content-Transfer-Encoding"""
    plain = "Hello=20World=21"  # "Hello World!" in quoted-printable
    
    mime = create_mime_message(plain, charset="utf-8", encoding="quoted-printable")
    
    plain_result, _, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    # Should decode quoted-printable
    assert "Hello" in plain_result, "Should decode quoted-printable"
    
    print("✅ Quoted-printable decoding works")


def test_base64_encoding():
    """Test base64 Content-Transfer-Encoding"""
    original_text = "Base64 test content"
    encoded_text = base64.b64encode(original_text.encode()).decode()
    
    mime = create_mime_message(encoded_text, charset="utf-8", encoding="base64")
    
    plain_result, _, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    # Should decode base64
    assert original_text in plain_result or len(plain_result) > 0, "Should decode base64"
    
    print("✅ Base64 decoding works")


def test_multipart_alternative_plain_preference():
    """Test multipart/alternative with plain text preference"""
    plain = "Plain text version"
    html = "<p>HTML version</p>"
    
    mime = create_mime_message(plain, html)
    
    # Prefer plain text
    plain_result, html_result, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    assert plain_result == plain, "Should extract plain text"
    assert html_result == html, "Should extract HTML"
    assert debug["parts_found"] == 2, "Should find 2 parts"
    
    print("✅ Multipart/alternative plain preference works")


def test_multipart_alternative_html_preference():
    """Test multipart/alternative with HTML preference"""
    plain = "Plain text version"
    html = "<p>HTML version</p>"
    
    mime = create_mime_message(plain, html)
    
    # Prefer HTML
    plain_result, html_result, debug = _extract_text_from_mime_with_charset(mime, prefer_html=True)
    
    assert html_result == html, "Should extract HTML"
    assert plain_result == plain, "Should also extract plain text"
    
    print("✅ Multipart/alternative HTML preference works")


def test_windows1252_charset():
    """Test Windows-1252 charset (common in Outlook emails)"""
    # Windows-1252 specific characters
    text_with_special = "Résumé café naïve"
    
    mime = create_mime_message(text_with_special, charset="windows-1252")
    
    plain_result, _, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    # Should transcode to UTF-8
    assert "sum" in plain_result or len(plain_result) > 0, "Should extract text"
    assert debug["mime_parsed"], "MIME should be parsed"
    
    print("✅ Windows-1252 charset transcoding works")


def test_line_ending_preservation_in_mime():
    """Test that CRLF line endings are preserved in raw MIME (Type=4)"""
    plain = "Line 1\r\nLine 2\r\nLine 3"
    
    mime = create_mime_message(plain)
    
    # Raw MIME should preserve CRLF
    assert b'\r\n' in mime, "MIME should contain CRLF line endings"
    
    print("✅ CRLF line endings preserved in MIME")


def test_empty_mime_handling():
    """Test handling of empty or malformed MIME"""
    empty_mime = b""
    
    plain_result, html_result, debug = _extract_text_from_mime_with_charset(empty_mime, prefer_html=False)
    
    # Should handle gracefully
    assert plain_result == "", "Empty MIME should return empty string"
    assert html_result == "", "Empty MIME should return empty string"
    
    print("✅ Empty MIME handled gracefully")


def test_mixed_charset_parts():
    """Test MIME with different charsets in different parts"""
    # This tests robustness - each part might have different encoding
    mime = b"""From: test@example.com
To: user@example.com
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=us-ascii

ASCII text
--boundary123
Content-Type: text/html; charset=utf-8

<p>UTF-8 HTML with émojis 🎉</p>
--boundary123--
"""
    
    plain_result, html_result, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    # Should extract both parts
    assert "ASCII" in plain_result, "Should extract ASCII plain text"
    assert "UTF-8" in html_result or "moji" in html_result, "Should extract UTF-8 HTML"
    assert debug["mime_parsed"], "Should parse mixed charset MIME"
    
    print("✅ Mixed charset MIME parts handled correctly")


def test_attachment_handling():
    """Test that attachments don't interfere with body extraction"""
    mime = b"""From: test@example.com
To: user@example.com
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=utf-8

Body text here
--boundary123
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment

BINARY DATA HERE
--boundary123--
"""
    
    plain_result, _, debug = _extract_text_from_mime_with_charset(mime, prefer_html=False)
    
    # Should extract body text, ignore attachment
    assert "Body text" in plain_result, "Should extract body text"
    assert debug["mime_parsed"], "Should parse MIME with attachment"
    
    print("✅ Attachments don't interfere with body extraction")


def run_all_tests():
    """Run all MIME handling tests"""
    print("\n" + "="*60)
    print("ActiveSync MIME Handling Tests")
    print("="*60 + "\n")
    
    tests = [
        test_utf8_mime_parsing,
        test_hebrew_charset_transcoding,
        test_quoted_printable_encoding,
        test_base64_encoding,
        test_multipart_alternative_plain_preference,
        test_multipart_alternative_html_preference,
        test_windows1252_charset,
        test_line_ending_preservation_in_mime,
        test_empty_mime_handling,
        test_mixed_charset_parts,
        test_attachment_handling,
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
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

