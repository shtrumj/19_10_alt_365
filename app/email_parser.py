"""
Email parsing utilities for displaying email content properly
"""

import base64
import binascii
import email
import email.policy
import hashlib
import html
import logging
import os
import quopri
import re
from email.header import decode_header, make_header
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def parse_email_content(raw_email_body):
    """
    Parse raw email content and extract the readable message body
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info("🔍 Starting email parsing...")
        logger.debug(f"Raw email length: {len(raw_email_body)} characters")
        logger.debug(f"Raw email preview: {raw_email_body[:200]}...")

        # First try to find actual content in the raw text (simpler approach)
        logger.info("📝 Attempting raw text extraction...")
        content = extract_content_from_raw(raw_email_body)
        logger.info(f"Raw extraction result: '{content}' (length: {len(content)})")

        if content and len(content.strip()) > 0:
            logger.info("✅ Raw extraction successful!")
            return content.strip()

        # If that fails, try parsing as proper email
        logger.info("📧 Attempting proper email parsing...")
        msg = email.message_from_string(raw_email_body)
        content = extract_main_content(msg)
        logger.info(f"Email parsing result: '{content}' (length: {len(content)})")

        if content and len(content.strip()) > 0:
            logger.info("✅ Email parsing successful!")
            return content.strip()

        # Fallback to basic cleaning
        logger.info("🧹 Attempting basic cleaning...")
        cleaned = clean_email_content(raw_email_body)
        logger.info(f"Basic cleaning result: '{cleaned}' (length: {len(cleaned)})")
        return cleaned

    except Exception as e:
        logger.error(f"❌ Error parsing email: {e}")
        logger.exception("Full traceback:")
        # Fallback to raw content with basic cleaning
        return clean_email_content(raw_email_body)


def extract_content_from_raw(raw_email):
    """
    Extract content directly from raw email text by looking for actual message parts
    """
    import logging

    logger = logging.getLogger(__name__)

    lines = raw_email.split("\n")
    content_lines = []
    in_content_section = False

    logger.debug(f"Processing {len(lines)} lines from raw email")

    for i, line in enumerate(lines):
        line = line.strip()

        # Look for the start of actual content sections
        if (
            "Content-Type: text/plain" in line
            or "Content-Type: text/html" in line
            or (line.startswith("--") and "boundary" in raw_email)
        ):
            logger.debug(f"Found content section start at line {i}: {line}")
            in_content_section = True
            continue

        # Look for the end of content sections
        if line.startswith("--") and in_content_section:
            logger.debug(f"Found content section end at line {i}: {line}")
            in_content_section = False
            continue

        # Only process lines when we're in a content section
        if in_content_section and line:
            logger.debug(f"Processing content line {i}: '{line}'")
            # Skip headers and encoded content
            if (
                not line.startswith(
                    (
                        "Content-Type:",
                        "Content-Transfer-Encoding:",
                        "From:",
                        "To:",
                        "Subject:",
                        "Date:",
                    )
                )
                and not re.match(r"^[A-Za-z0-9+/]{20,}={0,2}$", line)
                and not re.match(r"^[A-Za-z0-9+/]{20,}$", line)
                and (
                    not line.startswith("<")
                    or line.startswith("<div")
                    or line.startswith("<p")
                    or line.startswith("<span")
                )
            ):

                # This looks like actual content
                if len(line) > 2 and len(line) < 200:
                    logger.debug(f"Adding content line: '{line}'")
                    content_lines.append(line)

    logger.info(f"Found {len(content_lines)} content lines in sections")

    # If we didn't find content in sections, look for simple text patterns
    if not content_lines:
        logger.info("No content found in sections, trying simple text patterns...")
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for simple text that's not headers or encoded
            if (
                line
                and len(line) > 2
                and len(line) < 100
                and not line.startswith(
                    (
                        "From:",
                        "To:",
                        "Subject:",
                        "Date:",
                        "Received:",
                        "DKIM-",
                        "X-",
                        "MIME-",
                        "Content-",
                        "Message-ID:",
                        "References:",
                        "In-Reply-To:",
                    )
                )
                and not line.startswith("(")
                and not line.startswith("by ")
                and not line.startswith("for ")
                and not re.match(r"^[A-Za-z0-9+/]{10,}={0,2}$", line)
                and not re.match(r"^[A-Za-z0-9+/]{10,}$", line)
                and (
                    not any(char in line for char in ["=", "+", "/"])
                    or line.count("=") < 3
                )
            ):
                logger.debug(f"Adding simple text line {i}: '{line}'")
                content_lines.append(line)

    result = "\n".join(content_lines)
    logger.info(f"Final extraction result: '{result}' (length: {len(result)})")
    return result


def extract_main_content(msg):
    """
    Extract the main readable content from an email message
    """
    content = ""

    if msg.is_multipart():
        # Handle multipart messages - look for actual content parts
        for part in msg.walk():
            content_type = part.get_content_type()

            # Skip multipart containers and attachments
            if content_type.startswith("multipart/"):
                continue

            # Look for text content
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content = decode_payload(
                        payload, part.get_content_charset()
                    )
                    # Only use if it's actual content (not headers or encoded data)
                    if is_actual_content(decoded_content):
                        content = decoded_content
                        break
            elif content_type == "text/html" and not content:
                # Use HTML as fallback if no plain text found
                payload = part.get_payload(decode=True)
                if payload:
                    html_content = decode_payload(payload, part.get_content_charset())
                    if is_actual_content(html_content):
                        content = html_to_text(html_content)
                        break
    else:
        # Single part message
        payload = msg.get_payload(decode=True)
        if payload:
            content = decode_payload(payload, msg.get_content_charset())

    return content


def is_actual_content(text):
    """
    Check if text is actual message content (not headers or encoded data)
    """
    if not text or len(text.strip()) < 3:
        return False

    # Skip if it looks like headers
    if any(
        text.strip().startswith(header)
        for header in [
            "From:",
            "To:",
            "Subject:",
            "Date:",
            "Received:",
            "DKIM-",
            "X-",
            "MIME-",
            "Content-",
            "Message-ID:",
            "References:",
            "In-Reply-To:",
            "Return-Path:",
            "Delivered-To:",
            "Authentication-Results:",
        ]
    ):
        return False

    # Skip if it's mostly encoded data (base64, quoted-printable patterns)
    if len(text) > 50 and (
        text.count("=") > len(text) * 0.1
        or text.count("/") > len(text) * 0.1
        or text.count("+") > len(text) * 0.1
    ):
        return False

    # Skip if it's mostly special characters or very short
    if len(text.strip()) < 5:
        return False

    return True


def decode_payload(payload, charset=None):
    """
    Decode email payload with proper charset handling
    """
    try:
        if isinstance(payload, bytes):
            if charset:
                return payload.decode(charset, errors="ignore")
            else:
                return payload.decode("utf-8", errors="ignore")
        else:
            return str(payload)
    except Exception:
        return str(payload)


def clean_email_content(content):
    """
    Clean up email content by removing headers and encoded parts
    """
    if not content:
        return ""

    # Split into lines for processing
    lines = content.split("\n")
    cleaned_lines = []

    # Skip headers and look for actual content
    skip_headers = True
    found_content = False

    for line in lines:
        line = line.strip()

        # Stop skipping headers when we find actual content
        if skip_headers:
            # Check if this line looks like actual content (not headers)
            if (
                line
                and not line.startswith(
                    (
                        "From:",
                        "To:",
                        "Subject:",
                        "Date:",
                        "Received:",
                        "DKIM-",
                        "X-",
                        "MIME-",
                        "Content-",
                        "Message-ID:",
                        "References:",
                        "In-Reply-To:",
                        "Return-Path:",
                        "Delivered-To:",
                        "Authentication-Results:",
                    )
                )
                and not line.startswith(
                    "("
                )  # Skip lines like "(using TLS with cipher...)"
                and not line.startswith("by ")  # Skip "by mail-wr1-f45.google.com..."
                and not line.startswith("for ")  # Skip "for ; Sun, 28 Sep..."
                and not line.startswith("--")  # Skip MIME boundaries
                and not re.match(r"^[A-Za-z0-9+/]{20,}={0,2}$", line)  # Skip base64
                and not re.match(r"^[A-Za-z0-9+/]{20,}$", line)  # Skip encoded content
                and len(line) > 2
            ):  # Must be more than 2 characters
                skip_headers = False
                found_content = True

        # Add content lines
        if not skip_headers:
            # Skip empty lines at the beginning
            if not found_content and not line:
                continue
            found_content = True
            cleaned_lines.append(line)

    content = "\n".join(cleaned_lines)

    # Remove any remaining encoded content
    content = re.sub(r"^[A-Za-z0-9+/]{20,}={0,2}$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^[A-Za-z0-9+/]{20,}$", "", content, flags=re.MULTILINE)

    # Remove very long lines that look like encoded content
    content = re.sub(r"^.{100,}$", "", content, flags=re.MULTILINE)

    # Clean up multiple empty lines
    content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)

    # Remove trailing whitespace
    content = content.strip()

    return content


def html_to_text(html_content):
    """
    Basic HTML to text conversion
    """
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_content)

    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')

    return text


def _payload_to_bytes(part: Message) -> bytes:
    """Decode a message part payload to raw bytes, safely."""
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            text_payload = part.get_payload(decode=False)
            if isinstance(text_payload, str):
                charset = part.get_content_charset() or "utf-8"
                try:
                    return text_payload.encode(charset, errors="replace")
                except (LookupError, UnicodeEncodeError):
                    return text_payload.encode("utf-8", errors="replace")
            elif isinstance(text_payload, list):
                return b""
            else:
                return b""
        return payload
    except (binascii.Error, Exception):
        text_payload = part.get_payload(decode=False)
        if isinstance(text_payload, str):
            return text_payload.encode("utf-8", errors="replace")
        return b""


def _bytes_to_text(data: bytes, charset_hint: str | None) -> str:
    if not data:
        return ""
    charsets = [charset_hint, "utf-8", "latin-1"]
    for cs in charsets:
        if not cs:
            continue
        try:
            return data.decode(cs, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _extract_bodies_from_message(msg: Message) -> tuple[str, str]:
    text_candidates: list[str] = []
    html_candidates: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = part.get_content_type()
            if content_type == "text/plain":
                data = _payload_to_bytes(part)
                text_candidates.append(_bytes_to_text(data, part.get_content_charset()))
            elif content_type == "text/html":
                data = _payload_to_bytes(part)
                html_candidates.append(_bytes_to_text(data, part.get_content_charset()))
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            data = _payload_to_bytes(msg)
            text_candidates.append(_bytes_to_text(data, msg.get_content_charset()))
        elif content_type == "text/html":
            data = _payload_to_bytes(msg)
            html_candidates.append(_bytes_to_text(data, msg.get_content_charset()))

    text_body = ""
    html_body = ""

    if text_candidates:
        for candidate in text_candidates:
            if candidate and candidate.strip():
                text_body = candidate
                break
        if not text_body:
            text_body = text_candidates[0]

    if html_candidates:
        for candidate in html_candidates:
            if candidate and candidate.strip():
                html_body = candidate
                break
        if not html_body:
            html_body = html_candidates[0]

    if not text_body and html_body:
        text_body = html_to_text(html_body)

    return text_body.strip(), html_body.strip()


def _extract_attachments(msg: Message) -> list[dict[str, str | int]]:
    attachments: list[dict[str, str | int]] = []

    for part in msg.walk():
        if part.is_multipart():
            continue

        content_type = part.get_content_type()
        disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        content_id = (part.get("Content-ID") or "").strip()

        if content_id.startswith("<") and content_id.endswith(">"):
            content_id = content_id[1:-1]

        is_attachment = "attachment" in disposition
        is_inline_with_name = "inline" in disposition and filename
        is_cid_image = content_id and content_type.startswith("image/")

        if not (is_attachment or is_inline_with_name or is_cid_image):
            continue

        data = _payload_to_bytes(part)
        size = len(data)

        decoded_filename = ""
        if filename:
            try:
                decoded_filename = str(make_header(decode_header(filename)))
            except Exception:
                decoded_filename = filename

        attachments.append(
            {
                "filename": decoded_filename,
                "content_type": content_type,
                "size": size,
                "content_id": content_id,
            }
        )

    return attachments


def parse_mime_email(raw_email_body):
    """
    Advanced MIME email parsing for complex emails with pictures and attachments,
    leveraging Python's email.policy.default for robust decoding.
    """
    logger = logging.getLogger(__name__)

    try:
        logger.info("🔍 Starting advanced MIME parsing (policy.default)...")

        if isinstance(raw_email_body, bytes):
            raw_bytes = raw_email_body
        else:
            raw_bytes = raw_email_body.encode("utf-8", "ignore")

        try:
            msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
        except Exception:
            msg = email.message_from_string(raw_email_body, policy=email.policy.default)

        text_content, html_content = _extract_bodies_from_message(msg)
        attachments = _extract_attachments(msg)

        # Heuristic: if HTML part missing but text looks like raw HTML, promote it
        if not html_content and text_content:
            lowered = text_content.lower()
            if "<html" in lowered or "<body" in lowered:
                html_content = text_content

        # Heuristic: detect base64 blobs embedded in text/plain
        if not html_content and text_content:
            compact = re.sub(r"\s+", "", text_content)
            if (
                compact
                and len(compact) > 200
                and re.fullmatch(r"[A-Za-z0-9+/=]+", compact)
            ):
                try:
                    decoded_bytes = base64.b64decode(compact, validate=False)
                    decoded_text = decoded_bytes.decode("utf-8", errors="ignore")
                    if (
                        "<html" in decoded_text.lower()
                        or "<body" in decoded_text.lower()
                    ):
                        html_content = decoded_text
                        if not text_content or text_content == compact:
                            text_content = html_to_text(decoded_text)
                except Exception:
                    pass

        # Heuristic: if quoted-printable artifacts remain in text, attempt decode
        if (
            not html_content
            and text_content
            and ("=3D" in text_content or "=\r\n" in text_content)
        ):
            try:
                decoded_text = quopri.decodestring(
                    text_content.encode("utf-8", "ignore")
                ).decode("utf-8", errors="ignore")
                if "<html" in decoded_text.lower() or "<body" in decoded_text.lower():
                    html_content = decoded_text
                elif decoded_text.strip():
                    text_content = decoded_text
            except Exception:
                pass

        logger.info(
            "📝 MIME parse results -> text length: %s, html length: %s, attachments: %s",
            len(text_content),
            len(html_content),
            len(attachments),
        )

        # Prefer HTML for rich rendering
        if html_content and len(html_content.strip()) > 0:
            return {
                "content": html_content,
                "type": "html",
                "attachments": attachments,
            }

        if text_content and len(text_content.strip()) > 0:
            return {
                "content": text_content,
                "type": "text",
                "attachments": attachments,
            }

        # Last-resort: try quoted-printable decode of entire message
        try:
            qp_decoded = quopri.decodestring(raw_bytes).decode("utf-8", errors="ignore")
            if "<html" in qp_decoded.lower() or "<body" in qp_decoded.lower():
                return {
                    "content": qp_decoded,
                    "type": "html",
                    "attachments": attachments,
                }
            if qp_decoded.strip():
                return {
                    "content": qp_decoded.strip(),
                    "type": "text",
                    "attachments": attachments,
                }
        except Exception:
            pass

        logger.warning("⚠️ MIME parsing produced no readable content")
        return {
            "content": "No readable content found",
            "type": "none",
            "attachments": attachments,
        }

    except Exception as e:
        logger.error("❌ Error in MIME parsing: %s", e, exc_info=True)
        return {
            "content": "Error parsing email content",
            "type": "error",
            "attachments": [],
        }


def extract_text_from_mime(msg):
    """Extract plain text content from MIME message using safe built-in decoding."""
    logger = logging.getLogger(__name__)

    def decode_part(part):
        try:
            payload_bytes = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if payload_bytes is not None:
                return payload_bytes.decode(charset, errors="ignore")
            payload_str = part.get_payload()
            if isinstance(payload_str, str):
                cte = (part.get("Content-Transfer-Encoding", "") or "").lower()
                if cte == "quoted-printable":
                    return quopri.decodestring(
                        payload_str.encode("utf-8", "ignore")
                    ).decode(charset, errors="ignore")
                if cte == "base64":
                    return base64.b64decode(payload_str).decode(
                        charset, errors="ignore"
                    )
                return payload_str
        except Exception as e:
            logger.warning(f"Error decoding text/plain part: {e}")
        return ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                text = decode_part(part)
                if text:
                    logger.debug(f"Decoded text: {text[:100]}...")
                    return text
    else:
        if msg.get_content_type() == "text/plain":
            text = decode_part(msg)
            if text:
                logger.debug(f"Decoded single part text: {text[:100]}...")
                return text
    return ""


def extract_html_from_mime(msg):
    """Extract HTML content from MIME message using safe built-in decoding."""
    logger = logging.getLogger(__name__)

    def decode_part(part):
        try:
            payload_bytes = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if payload_bytes is not None:
                return payload_bytes.decode(charset, errors="ignore")
            payload_str = part.get_payload()
            if isinstance(payload_str, str):
                cte = (part.get("Content-Transfer-Encoding", "") or "").lower()
                if cte == "quoted-printable":
                    return quopri.decodestring(
                        payload_str.encode("utf-8", "ignore")
                    ).decode(charset, errors="ignore")
                if cte == "base64":
                    return base64.b64decode(payload_str).decode(
                        charset, errors="ignore"
                    )
                return payload_str
        except Exception as e:
            logger.warning(f"Error decoding text/html part: {e}")
        return ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_str = decode_part(part)
                if html_str:
                    logger.debug(f"Decoded HTML: {html_str[:100]}...")
                    return html_str
    else:
        if msg.get_content_type() == "text/html":
            html_str = decode_part(msg)
            if html_str:
                logger.debug(f"Decoded single part HTML: {html_str[:100]}...")
                return html_str
    return ""


def extract_attachments_from_mime(msg):
    """
    Extract attachment information from MIME message
    """
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            content_type = part.get_content_type()

            # Check if it's an attachment or inline image
            if "attachment" in content_disposition or (
                content_type.startswith("image/")
                or content_type.startswith("application/")
                or content_type.startswith("video/")
                or content_type.startswith("audio/")
            ):
                filename = part.get_filename()
                content_id = (part.get("Content-ID") or "").strip()
                if content_id.startswith("<") and content_id.endswith(">"):
                    content_id = content_id[1:-1]
                if filename:
                    # Decode filename if it's encoded
                    try:
                        decoded_filename = str(make_header(decode_header(filename)))
                        attachments.append(
                            {
                                "filename": decoded_filename,
                                "content_type": content_type,
                                "size": (len(part.get_payload(decode=True)) or 0),
                                "content_id": content_id,
                            }
                        )
                    except:
                        attachments.append(
                            {
                                "filename": filename,
                                "content_type": content_type,
                                "size": (len(part.get_payload(decode=True)) or 0),
                                "content_id": content_id,
                            }
                        )

    return attachments


def decode_quoted_printable(text):
    """
    Decode quoted-printable encoded text
    """
    try:
        return quopri.decodestring(text.encode()).decode("utf-8", errors="ignore")
    except:
        return text


def get_email_preview(email_body, max_length=100):
    """
    Get a clean preview of the email content
    """
    # Try advanced MIME parsing first
    mime_result = parse_mime_email(email_body)

    if mime_result["content"] and mime_result["content"] != "No readable content found":
        content = mime_result["content"]
    else:
        # Fallback to basic parsing
        content = parse_email_content(email_body)

    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "..."

    return content
