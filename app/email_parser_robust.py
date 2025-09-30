#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust MIME email parser for the 365 email system.
Based on production-grade parsing with proper handling of:
- RFC 2047 encoded headers
- Quoted-printable and base64 content
- Nested multiparts
- Hebrew and international text
"""

import base64
import binascii
import email
import email.policy
import email.utils
import hashlib
import logging
import re
from email.message import Message
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def decode_header_value(raw: Optional[str]) -> str:
    """Decode RFC 2047 encoded headers safely to str."""
    if not raw:
        return ""
    try:
        parts = email.header.decode_header(raw)
        out = []
        for text, enc in parts:
            if isinstance(text, bytes):
                try:
                    out.append(text.decode(enc or "utf-8", errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    out.append(text.decode("utf-8", errors="replace"))
            else:
                out.append(text)
        return "".join(out)
    except Exception:
        return raw


def strip_html(html: str) -> str:
    """Very lightweight HTML -> text fallback."""
    # Remove scripts/styles
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    # Replace breaks/paragraphs with newlines
    html = re.sub(r"(?i)</?(br|p|div|li|tr|td|th|h\d)>", "\n", html)
    # Remove all other tags
    html = re.sub(r"(?s)<[^>]+>", "", html)
    # Unescape basic entities
    html = html.replace("&nbsp;", " ")
    html = html.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    html = html.replace("&quot;", '"').replace("&#39;", "'")
    # Normalize whitespace
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n\s*\n\s*\n+", "\n\n", html)
    return html.strip()


def payload_to_bytes(part: Message) -> bytes:
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


def bytes_to_text(data: bytes, charset_hint: Optional[str]) -> str:
    """Decode bytes to text with charset fallback logic."""
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


def extract_bodies(msg: Message) -> Tuple[str, str]:
    """Extract text and HTML bodies."""
    text_candidates: List[str] = []
    html_candidates: List[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                data = payload_to_bytes(part)
                text_candidates.append(bytes_to_text(data, part.get_content_charset()))
            elif ctype == "text/html" and "attachment" not in disp:
                data = payload_to_bytes(part)
                html_candidates.append(bytes_to_text(data, part.get_content_charset()))
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            data = payload_to_bytes(msg)
            text_candidates.append(bytes_to_text(data, msg.get_content_charset()))
        elif ctype == "text/html":
            data = payload_to_bytes(msg)
            html_candidates.append(bytes_to_text(data, msg.get_content_charset()))

    text_body = ""
    html_body = ""

    if text_candidates:
        for t in text_candidates:
            if t.strip():
                text_body = t
                break
        if not text_body and text_candidates:
            text_body = text_candidates[0]
    if html_candidates:
        for h in html_candidates:
            if h.strip():
                html_body = h
                break
        if not html_body and html_candidates:
            html_body = html_candidates[0]

    if not text_body and html_body:
        text_body = strip_html(html_body)

    return (text_body.strip(), html_body.strip())


def parse_mime_email_robust(raw_email_body: str) -> Dict:
    """Robust MIME email parsing returning dict with content, type, attachments."""
    try:
        logger.info("🔍 Starting robust MIME parsing...")

        # Parse with policy for better handling
        msg = email.message_from_string(raw_email_body, policy=email.policy.default)

        # Extract subject
        subject = decode_header_value(msg.get("Subject"))
        logger.info(f"📧 Parsed subject: {subject}")

        # Extract bodies
        text_body, html_body = extract_bodies(msg)

        logger.info(f"📝 Text body length: {len(text_body)}")
        logger.info(f"🌐 HTML body length: {len(html_body)}")

        # Prefer HTML for rich rendering
        if html_body and len(html_body.strip()) > 10:
            logger.info("✅ Using HTML content (preferred)")
            return {
                "subject": subject,
                "content": html_body,
                "type": "html",
                "attachments": [],
            }
        elif text_body and len(text_body.strip()) > 10:
            logger.info("✅ Using text content (fallback)")
            return {
                "subject": subject,
                "content": text_body,
                "type": "text",
                "attachments": [],
            }
        else:
            logger.warning("⚠️ No suitable content found")
            return {
                "subject": subject,
                "content": "No readable content found",
                "type": "none",
                "attachments": [],
            }

    except Exception as e:
        logger.error(f"❌ Error in robust MIME parsing: {e}")
        logger.exception("Full traceback:")
        return {
            "subject": "(no subject)",
            "content": "Error parsing email content",
            "type": "error",
            "attachments": [],
        }
