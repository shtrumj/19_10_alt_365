#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wbxml_builder.py — Microsoft EAS 14.1-compliant WBXML builders.

Highlights
- AirSync (CP 0), Email (CP 2), AirSyncBase (CP 17) tokens.
- AirSyncBase <Body>: Type -> EstimatedDataSize -> Truncated -> Data.
- DateReceived always ends with 'Z' (UTC).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.parser import BytesParser
from email.utils import format_datetime, formatdate, make_msgid
from typing import Any, Dict, List, Optional

# WBXML control
SWITCH_PAGE = 0x00
END = 0x01
STR_I = 0x03

# Code pages
CP_AIRSYNC = 0
CP_PING = 1  # Ping codepage for push notifications
CP_EMAIL = 2
CP_AIRSYNCBASE = 17
CP_SETTINGS = 18  # Settings codepage for OOF, DeviceInformation, etc.
CP_PROVISION = 14

# AirSync (CP 0)
AS_Sync = 0x05
AS_Responses = 0x06
AS_Add = 0x07
AS_Change = 0x08
AS_Delete = 0x09
AS_Fetch = 0x0A
AS_SyncKey = 0x0B
AS_ClientId = 0x0C
AS_ServerId = 0x0D
AS_Status = 0x0E
AS_Collection = 0x0F
AS_Class = 0x10
AS_CollectionId = 0x12
AS_GetChanges = 0x13
AS_MoreAvailable = 0x14
AS_WindowSize = 0x15
AS_Commands = 0x16
AS_Collections = 0x1C
AS_ApplicationData = 0x1D
AS_ItemOperations = 0x1E
AS_Response = 0x1F
AS_Properties = 0x20

# Email (CP 2)
EM_DateReceived = 0x0F
EM_MessageClass = 0x13
EM_Subject = 0x14
EM_Read = 0x15
EM_To = 0x16
EM_From = 0x18
EM_InternetCPID = 0x39  # UTF-8 = 65001

# AirSyncBase (CP 17)
ASB_Type = 0x06
ASB_Body = 0x0A
ASB_Data = 0x0B
ASB_EstimatedDataSize = 0x0C
ASB_Truncated = 0x0D
ASB_ContentType = 0x0E
ASB_Preview = 0x14
ASB_NativeBodyType = 0x16

# Settings (CP 18) - MS-ASCMD § 2.2.2.1
SETTINGS_Settings = 0x05
SETTINGS_Status = 0x06
SETTINGS_Get = 0x07
SETTINGS_Set = 0x08
SETTINGS_Oof = 0x09
SETTINGS_OofState = 0x0A
SETTINGS_StartTime = 0x0B
SETTINGS_EndTime = 0x0C
SETTINGS_OofMessage = 0x0D
SETTINGS_AppliesToInternal = 0x0E
SETTINGS_AppliesToExternalKnown = 0x0F
SETTINGS_AppliesToExternalUnknown = 0x10
SETTINGS_Enabled = 0x11
SETTINGS_ReplyMessage = 0x12
SETTINGS_BodyType = 0x13
SETTINGS_DevicePassword = 0x14
SETTINGS_Password = 0x15
SETTINGS_DeviceInformation = 0x16
SETTINGS_Model = 0x17
SETTINGS_IMEI = 0x18
SETTINGS_FriendlyName = 0x19
SETTINGS_OS = 0x1A
SETTINGS_OSLanguage = 0x1B
SETTINGS_PhoneNumber = 0x1C
SETTINGS_UserInformation = 0x1D
SETTINGS_EmailAddresses = 0x1E
SETTINGS_SMTPAddress = 0x1F
SETTINGS_UserAgent = 0x20
SETTINGS_EnableOutboundSMS = 0x21
SETTINGS_MobileOperator = 0x22
SETTINGS_PrimarySmtpAddress = 0x23
SETTINGS_Accounts = 0x24
SETTINGS_Account = 0x25
SETTINGS_AccountId = 0x26
SETTINGS_AccountName = 0x27
SETTINGS_UserDisplayName = 0x28
SETTINGS_SendDisabled = 0x29
SETTINGS_RightsManagementInformation = 0x2B


class WBXMLWriter:
    def __init__(self):
        self.buf = bytearray()
        self.cur_page = 0xFFFF

    def header(self):
        # WBXML v1.3, public id 0x01 (unknown), charset UTF-8 (0x6A), string table = 0
        self.buf.extend([0x03, 0x01, 0x6A, 0x00])

    def write_byte(self, b: int):
        self.buf.append(b & 0xFF)

    def write_str(self, s: str):
        self.write_byte(STR_I)
        self.buf.extend(s.encode("utf-8"))
        self.write_byte(0x00)

    def write_opaque(self, data_bytes: bytes):
        """Write OPAQUE block (WBXML token 0xC3 + mb_u_int32 length + raw bytes)"""
        # 0xC3 = OPAQUE
        self.buf.append(0xC3)
        # write WBXML multibyte length (mb_u_int32)
        n = len(data_bytes)
        stack = []
        while True:
            stack.append(n & 0x7F)
            n >>= 7
            if n == 0:
                break
        while stack:
            b = stack.pop()
            if stack:
                b |= 0x80
            self.buf.append(b)
        self.buf.extend(data_bytes)

    def page(self, cp: int):
        if self.cur_page != cp:
            self.write_byte(SWITCH_PAGE)
            self.write_byte(cp & 0xFF)
            self.cur_page = cp

    # Alias to match older call sites
    def cp(self, cp: int):
        self.page(cp)

    def start(self, tok: int, with_content: bool = True):
        self.write_byte((tok | 0x40) if with_content else tok)

    def end(self):
        self.write_byte(END)

    def bytes(self) -> bytes:
        return bytes(self.buf)


def _ensure_utc_z(dt_or_str: Any) -> str:
    if isinstance(dt_or_str, datetime):
        return (
            dt_or_str.astimezone(timezone.utc)
            .replace(tzinfo=None)
            .isoformat(timespec="milliseconds")
            + "Z"
        )
    if isinstance(dt_or_str, str):
        s = dt_or_str
        if not s.endswith("Z"):
            # best-effort: append 'Z' if missing
            if "T" in s:
                # strip fractional if any to keep things tidy
                main = s.split(".")[0]
                return main + ".000Z"
            return s + "Z"
        return s
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000") + "Z"


@dataclass
class SyncBatch:
    response_sync_key: str
    payload: bytes
    sent_count: int
    total_available: int
    more_available: bool


def _select_body_content(
    em: Dict[str, Any], body_type_preference: int = 2
) -> tuple[str, int]:
    """
    Choose body content according to BodyPreference:
    - 2 => HTML preferred (if available), else plain
    - 1 => Plain preferred (if available), else HTML
    Returns (content, native_type), where native_type: 1=Plain, 2=HTML
    """
    html = str(em.get("body_html") or em.get("html") or "")
    plain = str(em.get("body") or em.get("preview") or "")
    if body_type_preference == 1:
        content = plain or html
        native = 1 if plain else 2 if html else 1
    else:
        content = html or plain
        native = 2 if html else 1 if plain else 1
    return content, native


def _truncate_bytes(data: bytes, limit: Optional[int]) -> tuple[bytes, str]:
    if not data:
        return data, "0"
    if limit is None:
        return data, "0"
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        return data, "0"
    if limit_int <= 0 or len(data) <= limit_int:
        return data, "0"
    return data[:limit_int], "1"


# UTF-8 safe truncation for text payloads
# Ensures we don't cut inside a multibyte sequence
# Returns (bytes, truncated_flag)


def _truncate_utf8_bytes(data: bytes, limit: Optional[int]) -> tuple[bytes, str]:
    if not data:
        return data, "0"
    if limit is None:
        return data, "0"
    try:
        n = int(limit)
    except (ValueError, TypeError):
        return data, "0"
    if n <= 0 or len(data) <= n:
        return data, "0"
    # Backtrack from n to the start of a UTF-8 character boundary
    end = n
    # While byte is a continuation (10xxxxxx), move back
    while end > 0 and (data[end - 1] & 0xC0) == 0x80:
        end -= 1
    # Safety: if we backed into leading bytes incorrectly, try decode fallback
    candidate = data[:end]
    try:
        candidate.decode("utf-8")
        return candidate, "1"
    except UnicodeDecodeError:
        # Fallback: strip a few bytes until decodable or empty
        while end > 0:
            end -= 1
            candidate = data[:end]
            try:
                candidate.decode("utf-8")
                return candidate, "1"
            except UnicodeDecodeError:
                continue
        return b"", "1"


def _format_email_date(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "")
        try:
            if text.endswith("Z"):
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(text)
        except Exception:
            dt = datetime.utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _build_mime_message(em: Dict[str, Any], html_body: str, plain_body: str) -> bytes:
    """Build a proper MIME message for ActiveSync body_type 4 responses."""
    msg = MIMEMultipart("alternative")

    subject = str(em.get("subject") or "")
    if subject:
        msg["Subject"] = subject

    from_addr = str(em.get("from") or em.get("sender") or "")
    to_addr = str(em.get("to") or em.get("recipient") or "")
    if from_addr:
        msg["From"] = from_addr
    if to_addr:
        msg["To"] = to_addr

    created_at = em.get("created_at")
    try:
        msg["Date"] = _format_email_date(created_at)
    except Exception:
        msg["Date"] = formatdate(localtime=True)

    msg["Message-ID"] = em.get("message_id") or make_msgid()

    # Add MIME-Version header (required for proper MIME parsing)
    msg["MIME-Version"] = "1.0"

    # Add Content-Type header for multipart/alternative
    msg["Content-Type"] = 'multipart/alternative; boundary="{}"'.format(
        msg.get_boundary()
    )

    # Attach parts in order: plain text first, then HTML
    if plain_body:
        plain_part = MIMEText(plain_body, "plain", "utf-8")
        plain_part["Content-Type"] = "text/plain; charset=utf-8"
        msg.attach(plain_part)

    if html_body:
        html_part = MIMEText(html_body, "html", "utf-8")
        html_part["Content-Type"] = "text/html; charset=utf-8"
        msg.attach(html_part)

    # Ensure we have at least one part
    if not msg.get_payload():
        plain_part = MIMEText("", "plain", "utf-8")
        plain_part["Content-Type"] = "text/plain; charset=utf-8"
        msg.attach(plain_part)

    return msg.as_bytes(policy=policy.SMTP)


def _extract_text_from_mime_with_charset(
    mime_bytes: bytes, prefer_html: bool = False
) -> tuple[str, str, dict]:
    """
    Z-Push/Grommunio-style robust MIME body extraction with charset transcoding.

    Returns:
        (plain_text, html_text, debug_info)
    """
    import email
    from email import policy

    debug_info = {
        "mime_parsed": False,
        "parts_found": 0,
        "charsets_detected": [],
        "content_types": [],
        "transcoding_errors": [],
    }

    try:
        msg = email.message_from_bytes(mime_bytes, policy=policy.default)
        debug_info["mime_parsed"] = True

        plain_parts = []
        html_parts = []

        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                content_type = part.get_content_type()
                charset = part.get_content_charset() or "utf-8"

                debug_info["parts_found"] += 1
                debug_info["content_types"].append(content_type)
                debug_info["charsets_detected"].append(charset)

                # Skip attachments
                disposition = str(part.get("Content-Disposition") or "").lower()
                if "attachment" in disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        # Get raw payload bytes (handles base64, quoted-printable, etc.)
                        payload_bytes = part.get_payload(decode=True)
                        if not payload_bytes:
                            continue

                        # CRITICAL: Transcode from source charset to UTF-8
                        try:
                            decoded_text = payload_bytes.decode(
                                charset, errors="replace"
                            )
                        except (UnicodeDecodeError, LookupError):
                            # Fallback charsets for broken/incorrect declarations
                            for fallback_charset in [
                                "utf-8",
                                "latin-1",
                                "windows-1252",
                                "windows-1255",
                            ]:
                                try:
                                    decoded_text = payload_bytes.decode(
                                        fallback_charset, errors="replace"
                                    )
                                    debug_info["transcoding_errors"].append(
                                        f"Fallback to {fallback_charset} for {charset}"
                                    )
                                    break
                                except (UnicodeDecodeError, LookupError):
                                    continue
                            else:
                                decoded_text = payload_bytes.decode(
                                    "utf-8", errors="replace"
                                )

                        plain_parts.append(decoded_text)
                    except Exception as e:
                        debug_info["transcoding_errors"].append(f"text/plain: {str(e)}")

                elif content_type == "text/html":
                    try:
                        payload_bytes = part.get_payload(decode=True)
                        if not payload_bytes:
                            continue

                        # CRITICAL: Transcode from source charset to UTF-8
                        try:
                            decoded_text = payload_bytes.decode(
                                charset, errors="replace"
                            )
                        except (UnicodeDecodeError, LookupError):
                            for fallback_charset in [
                                "utf-8",
                                "latin-1",
                                "windows-1252",
                                "windows-1255",
                            ]:
                                try:
                                    decoded_text = payload_bytes.decode(
                                        fallback_charset, errors="replace"
                                    )
                                    debug_info["transcoding_errors"].append(
                                        f"Fallback to {fallback_charset} for {charset}"
                                    )
                                    break
                                except (UnicodeDecodeError, LookupError):
                                    continue
                            else:
                                decoded_text = payload_bytes.decode(
                                    "utf-8", errors="replace"
                                )

                        html_parts.append(decoded_text)
                    except Exception as e:
                        debug_info["transcoding_errors"].append(f"text/html: {str(e)}")
        else:
            # Single-part message
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or "utf-8"

            debug_info["parts_found"] = 1
            debug_info["content_types"].append(content_type)
            debug_info["charsets_detected"].append(charset)

            try:
                payload_bytes = msg.get_payload(decode=True)
                if payload_bytes:
                    try:
                        decoded_text = payload_bytes.decode(charset, errors="replace")
                    except (UnicodeDecodeError, LookupError):
                        decoded_text = payload_bytes.decode("utf-8", errors="replace")

                    if content_type == "text/plain":
                        plain_parts.append(decoded_text)
                    elif content_type == "text/html":
                        html_parts.append(decoded_text)
            except Exception as e:
                debug_info["transcoding_errors"].append(f"single-part: {str(e)}")

        plain_text = "\n\n".join(plain_parts) if plain_parts else ""
        html_text = "\n\n".join(html_parts) if html_parts else ""

        return plain_text, html_text, debug_info

    except Exception as e:
        debug_info["transcoding_errors"].append(f"parse_failed: {str(e)}")
        return "", "", debug_info


def _validate_body_payload(payload: dict, requested_type: int) -> None:
    """
    Validate body payload compliance with MS-ASAIRS specification.

    References:
    - MS-ASAIRS §2.2.2.17: EstimatedDataSize (MUST be untruncated size)
    - MS-ASAIRS §2.2.2.50: Truncated (0 or 1)
    - MS-ASAIRS §2.2.2.22.7: Type (1=plain, 2=HTML, 3=RTF, 4=MIME)
    - MS-ASAIRS §2.2.2.8: Data (inline or OPAQUE)
    """
    from app.diagnostic_logger import _write_json_line

    # Required fields per MS-ASAIRS
    assert "type" in payload, "MS-ASAIRS violation: Missing Body.Type"
    assert (
        "data" in payload or "data_bytes" in payload
    ), "MS-ASAIRS violation: Missing Body.Data"
    assert (
        "estimated_size" in payload
    ), "MS-ASAIRS violation: Missing Body.EstimatedDataSize"
    assert "truncated" in payload, "MS-ASAIRS violation: Missing Body.Truncated"

    # Truncated must be "0" or "1" (standard truncation only)
    # We don't use Truncated=2 as it's non-standard and breaks iOS
    assert payload["truncated"] in (
        "0",
        "1",
    ), f"MS-ASAIRS violation: Truncated must be '0' or '1', got '{payload['truncated']}'"

    # Calculate actual data size
    if "data" in payload:
        actual_size = len(payload["data"].encode("utf-8"))
    elif "data_bytes" in payload:
        actual_size = len(payload["data_bytes"])
    else:
        actual_size = 0

    estimated = int(payload["estimated_size"])

    # MS-ASAIRS §2.2.2.17: EstimatedDataSize MUST be >= actual data size when truncated
    if payload["truncated"] == "1":
        assert (
            estimated >= actual_size
        ), f"MS-ASAIRS violation: EstimatedDataSize ({estimated}) < actual ({actual_size})"

    # Log validation success
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "body_payload_validated",
            "type": payload["type"],
            "estimated_size": estimated,
            "actual_data_size": actual_size,
            "truncated": payload["truncated"],
            "ms_asairs_compliant": True,
        },
    )


def _prepare_body_payload(
    em: Dict[str, Any],
    *,
    requested_type: int = 2,
    truncation_size: Optional[int] = None,
) -> Dict[str, str]:
    # CRITICAL FIX: If MIME content is available, parse it with proper charset handling
    # This prevents "Loading..." issues on iPhone caused by encoding mismatches
    mime_bytes = em.get("mime_content")

    # DEBUG: Log MIME availability
    from app.diagnostic_logger import _write_json_line

    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "body_payload_prep_start",
            "email_id": em.get("id"),
            "requested_type": requested_type,
            "truncation_size_param": truncation_size,  # DEBUG: Log the parameter value!
            "has_mime_content": bool(mime_bytes),
            "mime_content_type": type(mime_bytes).__name__ if mime_bytes else None,
            "mime_length": len(mime_bytes) if mime_bytes else 0,
        },
    )

    if mime_bytes and requested_type in (1, 2):
        # We have MIME content and client wants text/HTML (not raw MIME)
        # Parse with robust charset transcoding
        if isinstance(mime_bytes, str):
            try:
                mime_bytes = base64.b64decode(mime_bytes)
            except Exception:
                mime_bytes = mime_bytes.encode("utf-8", errors="ignore")

        plain_from_mime, html_from_mime, debug_info = (
            _extract_text_from_mime_with_charset(
                mime_bytes, prefer_html=(requested_type == 2)
            )
        )

        # Log charset transcoding for debugging
        from app.diagnostic_logger import _write_json_line

        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "mime_charset_transcoding",
                "requested_type": requested_type,
                "mime_parsed": debug_info["mime_parsed"],
                "parts_found": debug_info["parts_found"],
                "charsets_detected": debug_info["charsets_detected"],
                "content_types": debug_info["content_types"],
                "transcoding_errors": debug_info["transcoding_errors"],
                "plain_length": len(plain_from_mime),
                "html_length": len(html_from_mime),
            },
        )

        # Use the transcoded content
        if plain_from_mime or html_from_mime:
            html = html_from_mime
            plain = plain_from_mime
        else:
            # Fallback to pre-stored fields if MIME parsing failed
            html = str(em.get("body_html") or em.get("html") or "")
            plain = str(em.get("body") or em.get("preview") or "")
    else:
        # No MIME content or Type 4 request - use pre-stored fields
        html = str(em.get("body_html") or em.get("html") or "")
        plain = str(em.get("body") or em.get("preview") or "")

    body_type = requested_type if requested_type in (1, 2, 4) else 2

    if body_type == 4:
        mime_bytes = em.get("mime_content")
        if mime_bytes:
            if isinstance(mime_bytes, str):
                # MIME content in DB is base64 encoded - decode it first
                try:
                    mime_bytes = base64.b64decode(mime_bytes)
                except Exception:
                    # If decode fails, treat as raw bytes
                    mime_bytes = mime_bytes.encode("utf-8", errors="ignore")
        else:
            mime_bytes = _build_mime_message(em, html, plain)

        detected_mime_header = ""
        parsed_message: Message | None = None
        try:
            parsed_message = BytesParser(policy=policy.default).parsebytes(mime_bytes)
            detected_mime_header = parsed_message.get("Content-Type") or ""
        except Exception:
            parsed_message = None

        mime_content_type = str(em.get("mime_content_type") or "").strip()
        if not mime_content_type:
            if detected_mime_header:
                mime_content_type = detected_mime_header
            elif parsed_message:
                try:
                    mime_content_type = parsed_message.get_content_type() or ""
                except Exception:
                    mime_content_type = ""

        estimated_size = str(len(mime_bytes))
        payload_bytes, truncated_flag = _truncate_bytes(mime_bytes, truncation_size)

        # Z-Push sends NativeBodyType=1 (plain) or 2 (HTML) even when Type=4 (MIME)
        _, native_pref = _select_body_content(em, 2)
        native_type = "2" if native_pref == 2 else "1"

        # For Type=4, we need to return the raw bytes for OPAQUE writing
        # DEBUG: Log type=4 MIME body data
        from app.diagnostic_logger import _write_json_line

        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "mime_type4_body_final",
                "email_id": em.get("id"),
                "data_bytes_length": len(payload_bytes) if payload_bytes else 0,
                "data_is_empty": not bool(payload_bytes),
                "estimated_size": estimated_size,
                "truncated": truncated_flag,
                "native_type": native_type,
                "mime_content_type": mime_content_type or detected_mime_header,
                "data_preview_hex": (
                    payload_bytes[:100].hex() if payload_bytes else None
                ),
            },
        )

        payload = {
            "type": "4",
            "data_bytes": payload_bytes,  # Raw bytes for OPAQUE
            "estimated_size": estimated_size,
            "truncated": truncated_flag,
            "native_type": native_type,
            "content_type": "message/rfc822",
            "detected_mime_type": mime_content_type or detected_mime_header,
        }

        # MS-ASAIRS COMPLIANCE VALIDATION
        _validate_body_payload(payload, requested_type=4)

        return payload

    preference = 1 if body_type == 1 else 2

    # CRITICAL FIX: Use the transcoded MIME content, not pre-stored fields!
    # The html/plain variables were populated by MIME transcoding above
    if preference == 1:
        # Client wants plain text
        content = plain or html
        selected_native = 1 if plain else 2 if html else 1
    else:
        # Client wants HTML
        content = html or plain
        selected_native = 2 if html else 1 if plain else 1

    # DEBUG: Log what content was selected
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "body_content_selected",
            "email_id": em.get("id"),
            "preference": preference,
            "selected_native": selected_native,
            "has_plain": bool(plain),
            "has_html": bool(html),
            "plain_length": len(plain) if plain else 0,
            "html_length": len(html) if html else 0,
            "selected_content_length": len(content) if content else 0,
            "content_preview": content[:100] if content else None,
        },
    )

    # Z-PUSH STRATEGY: Calculate EstimatedDataSize BEFORE any modifications
    # EstimatedDataSize MUST be the size of the FULL (untruncated) body with original line endings
    # per MS-ASCMD § 2.2.2.17
    original_body_bytes = content.encode("utf-8") if content else b""
    estimated_size = str(len(original_body_bytes))  # ✅ FULL size, not truncated!

    # Z-PUSH STRATEGY: Normalize line endings for Type=1/2 (text/HTML) AFTER size calculation
    # iPhone rejects plain text bodies with CRLF (\r\n), expects LF (\n) only
    # But keep original line endings in EstimatedDataSize calculation
    if content:
        content = content.replace("\r\n", "\n")  # CRLF -> LF
        content = content.replace("\r", "\n")  # CR -> LF (for old Mac emails)

    # Z-PUSH STRATEGY: Honor client's TruncationSize exactly, no artificial limits
    # Truncate at UTF-8 byte boundaries to prevent corruption
    body_bytes = content.encode("utf-8") if content else b""

    # DEBUG: Log truncation decision
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "truncation_check",
            "truncation_size": truncation_size,
            "content_length_bytes": len(body_bytes),
            "original_body_size_bytes": len(original_body_bytes),
            "estimated_size": estimated_size,
            "will_truncate": bool(
                truncation_size and len(body_bytes) > truncation_size
            ),
        },
    )

    if truncation_size and len(body_bytes) > truncation_size:
        # Truncate at UTF-8 character boundary (prevents multi-byte character corruption)
        payload_bytes, truncated_flag = _truncate_utf8_bytes(
            body_bytes, truncation_size
        )
    else:
        payload_bytes = body_bytes
        truncated_flag = "0"

    data_text = payload_bytes.decode("utf-8", errors="strict") if payload_bytes else ""

    actual_type = "2" if (content and selected_native == 2 and data_text) else "1"

    # CRITICAL: Following grommunio-sync implementation
    # Do NOT wrap HTML in complete documents - send fragments as-is
    # grommunio-sync sends raw HTML fragments, and iOS Mail handles them correctly
    # when properly encoded in WBXML with correct charset (UTF-8)

    # HTML wrapping DISABLED - testing raw HTML fragments per grommunio-sync
    # if actual_type == "2" and data_text:
    #     if not data_text.strip().lower().startswith("<!doctype") and not data_text.strip().lower().startswith("<html"):
    #         data_text = f"""<!DOCTYPE html>..."""
    #         estimated_size = str(len(data_text.encode("utf-8")))

    content_type = (
        "text/html; charset=utf-8"
        if actual_type == "2"
        else "text/plain; charset=utf-8"
    )
    native_type = "2" if selected_native == 2 else "1"

    # CRITICAL FIX: For small truncations (≤5120 bytes), use Preview-only mode
    # REMOVED: Preview-only mode (Truncated=2) is NOT standard and breaks iOS
    # Standard servers (grommunio-sync, z-push) simply truncate HTML and send in Data element
    # No preview_only flag, no Truncated=2, no Preview element

    # DEBUG: Log the final body data being returned
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "body_data_final",
            "email_id": em.get("id"),
            "actual_type": actual_type,
            "native_type": native_type,
            "data_length": len(data_text),
            "data_is_empty": not bool(data_text),
            "data_preview": data_text[:100] if data_text else None,
            "truncated": truncated_flag,
        },
    )

    payload = {
        "type": actual_type,
        "data": data_text,
        "estimated_size": estimated_size,
        "truncated": truncated_flag,
        "native_type": native_type,
        "content_type": content_type,
    }

    # MS-ASAIRS COMPLIANCE VALIDATION
    _validate_body_payload(payload, requested_type=body_type)

    return payload


def write_fetch_responses(
    *,
    w: WBXMLWriter,
    fetched: List[Dict[str, Any]],
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> None:
    """Emit canonical <Responses><Fetch> blocks (Z-Push order) with proper body and no CollectionId."""
    if not fetched:
        return

    # DEBUG: Log fetch response building
    from app.diagnostic_logger import _write_json_line

    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "write_fetch_responses_start",
            "fetched_count": len(fetched),
            "fetched_ids": [em.get("id") for em in fetched],
            "body_type_preference": body_type_preference,
            "truncation_size": truncation_size,
        },
    )

    w.cp(CP_AIRSYNC)
    w.start(AS_Responses)
    for em in fetched:
        server_id = str(em.get("server_id") or em.get("id") or "")
        if not server_id:
            continue
        # <Fetch>
        w.start(AS_Fetch)
        # ORDER: ServerId -> Status -> Class -> ApplicationData
        w.start(AS_ServerId)
        w.write_str(server_id)
        w.end()
        w.start(AS_Status)
        w.write_str("1")
        w.end()
        w.start(AS_Class)
        w.write_str("Email")
        w.end()
        # <ApplicationData>
        w.start(AS_ApplicationData)
        # Optional envelope
        w.cp(CP_EMAIL)
        subj = str(em.get("subject") or "")
        frm = str(em.get("from") or em.get("sender") or "")
        to = str(em.get("to") or em.get("recipient") or "")
        when = _ensure_utc_z(em.get("created_at"))
        if subj:
            w.start(EM_Subject)
            w.write_str(subj)
            w.end()
        if frm:
            w.start(EM_From)
            w.write_str(frm)
            w.end()
        if to:
            w.start(EM_To)
            w.write_str(to)
            w.end()
        if when:
            w.start(EM_DateReceived)
            w.write_str(when)
            w.end()
        w.start(EM_MessageClass)
        w.write_str("IPM.Note")
        w.end()
        w.start(EM_InternetCPID)
        w.write_str("65001")
        w.end()
        # Body (respect preference & truncation)
        body_payload = _prepare_body_payload(
            em,
            requested_type=body_type_preference,
            truncation_size=truncation_size,
        )
        w.cp(CP_AIRSYNCBASE)
        w.start(ASB_Body)
        w.start(ASB_Type)
        w.write_str(body_payload["type"])
        w.end()
        w.start(ASB_EstimatedDataSize)
        w.write_str(body_payload["estimated_size"])
        w.end()
        w.start(ASB_Truncated)
        w.write_str(body_payload["truncated"])
        w.end()
        w.start(ASB_Data)
        if body_payload["type"] == "4" and "data_bytes" in body_payload:
            # Type=4 (MIME) uses OPAQUE bytes
            w.write_opaque(body_payload["data_bytes"])
        else:
            # Type=1/2 uses string data
            if body_payload["type"] == "4" and "data_bytes" in body_payload:
                # Type=4 (MIME) uses OPAQUE bytes
                w.write_opaque(body_payload["data_bytes"])
            else:
                # Type=1/2 uses string data
                # DEBUG: Log what's being written to WBXML
                from app.diagnostic_logger import _write_json_line

                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "wbxml_body_data_write",
                        "body_type": body_payload["type"],
                        "data_length": (
                            len(body_payload["data"]) if body_payload.get("data") else 0
                        ),
                        "data_is_empty": not bool(body_payload.get("data")),
                        "data_preview": (
                            body_payload["data"][:100]
                            if body_payload.get("data")
                            else None
                        ),
                        "encoding": "opaque_utf8",
                    },
                )
                # CRITICAL iOS FIX: Type=1/2 MUST use OPAQUE (not STR_I) per iOS requirements
                w.write_opaque(body_payload["data"].encode("utf-8"))
        w.end()

        # CRITICAL FIX: Send Preview INSTEAD OF Data for small truncations
        # Per MS-ASCMD §2.2.3.35.2: Preview is for email list view (header-only sync)
        # When client requests small truncation (≤512 bytes), send Preview, not Data
        # When client requests large truncation or full body, send Data
        # NEVER send both Preview and Data together!

        # Old disabled Preview logic below (kept for reference)
        if False:  # DISABLED: This block is for old Preview-only logic
            preview_text = body_payload["data"][:255]  # First 255 chars

            # DEBUG: Log Preview write attempt (Fetch path)
            from app.diagnostic_logger import _write_json_line

            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "wbxml_preview_write_attempt_fetch",
                    "preview_length": len(preview_text),
                    "preview_preview": preview_text[:50],
                    "body_type": body_payload["type"],
                    "is_truncated": body_payload.get("truncated"),
                },
            )

            w.start(ASB_Preview)
            w.write_str(preview_text)
            w.end()

            # DEBUG: Confirm Preview written
            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "wbxml_preview_written_fetch",
                    "preview_length": len(preview_text),
                },
            )
        else:
            # Preview skipped (truncated or no data)
            from app.diagnostic_logger import _write_json_line

            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "preview_skipped_fetch",
                    "reason": "truncated_or_no_data",
                    "has_data": bool(body_payload.get("data")),
                    "is_truncated": body_payload.get("truncated"),
                },
            )

        # REMOVED: ContentType should NOT be in Body element per MS-ASAIRS spec
        # MS-ASAIRS § 2.2.2.9: ContentType is for attachments only
        # Having it in main body may confuse iOS Mail
        # content_type = body_payload.get("content_type")
        # if content_type:
        #     w.start(ASB_ContentType)
        #     w.write_str(content_type)
        #     w.end()
        w.end()  # </Body>
        w.start(ASB_NativeBodyType)
        w.write_str(body_payload["native_type"])
        w.end()
        # Close ApplicationData and Fetch
        w.cp(CP_AIRSYNC)
        w.end()  # </ApplicationData>
        w.end()  # </Fetch>
    w.end()  # </Responses>

    # DEBUG: Log fetch response completion
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "write_fetch_responses_complete",
            "fetched_count": len(fetched),
            "fetched_ids": [em.get("id") for em in fetched],
        },
    )


def write_delete_responses(
    *,
    w: WBXMLWriter,
    deletes: List[Dict[str, Any]],
) -> None:
    """Emit <Responses><Delete> acknowledgements."""
    if not deletes:
        return
    w.cp(CP_AIRSYNC)
    w.start(AS_Responses)
    for item in deletes:
        sid = str(item.get("server_id") or "")
        status = str(item.get("status") or "1")
        # <Delete>
        w.start(AS_Delete)
        w.start(AS_Status)
        w.write_str(status)
        w.end()
        w.start(AS_ServerId)
        w.write_str(sid)
        w.end()
        w.end()  # </Delete>
    w.end()  # </Responses>


def build_sync_response(
    *,
    new_sync_key: str,
    class_name: str,
    collection_id: str,
    items: List[Dict[str, Any]],
    window_size: int,
    more_available: bool,
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    <Sync>
      <Status>1</Status>
      <Collections>
        <Collection>
          <SyncKey>...</SyncKey>
          <CollectionId>...</CollectionId>
          <Status>1</Status>
          <Class>Email</Class>
          [<MoreAvailable/>]
          <Commands>
            <Add>
              <ServerId>...</ServerId>
              <ApplicationData>
                Email:*
                AirSyncBase:Body
              </ApplicationData>
            </Add>
            ...
          </Commands>
        </Collection>
      </Collections>
    </Sync>
    """
    w = WBXMLWriter()
    w.header()

    # <Sync>
    w.page(CP_AIRSYNC)
    w.start(AS_Sync)

    # CRITICAL: MS-ASCMD requires top-level Status BEFORE Collections!
    # <Status>1</Status>
    w.start(AS_Status)
    w.write_str("1")
    w.end()

    # <Collections><Collection>
    w.start(AS_Collections)
    w.start(AS_Collection)

    # CRITICAL FIX: Correct MS-ASCMD order - Status MUST come BEFORE Class!
    # Microsoft spec: SyncKey -> CollectionId -> Status -> Class
    w.start(AS_SyncKey)
    w.write_str(new_sync_key)
    w.end()
    w.start(AS_CollectionId)
    w.write_str(str(collection_id))
    w.end()
    w.start(AS_Status)
    w.write_str("1")
    w.end()
    w.start(AS_Class)
    w.write_str(class_name)
    w.end()

    count = 0
    if items:
        # Commands
        w.start(AS_Commands)

        for idx, em in enumerate(items):
            if count >= window_size:
                break

            server_id = em.get("server_id") or f"{collection_id}:{em.get('id', idx+1)}"
            subj = em.get("subject") or "(no subject)"
            from_ = em.get("from") or em.get("sender") or ""
            to_ = em.get("to") or em.get("recipient") or ""
            read = "1" if bool(em.get("is_read")) else "0"
            when = _ensure_utc_z(em.get("created_at"))

            body_payload = _prepare_body_payload(
                em,
                requested_type=body_type_preference,
                truncation_size=truncation_size,
            )

            # <Add>
            w.page(CP_AIRSYNC)
            w.start(AS_Add)

            # <ServerId>
            w.start(AS_ServerId)
            w.write_str(server_id)
            w.end()

            # DEBUG: log ServerId emitted in Add
            try:
                from app.diagnostic_logger import _write_json_line as _dj

                _dj(
                    "activesync/activesync.log",
                    {
                        "event": "sync_add_server_id",
                        "server_id": server_id,
                        "email_id": em.get("id"),
                        "collection_id": collection_id,
                    },
                )
            except Exception:
                pass

            # <ApplicationData>
            w.start(AS_ApplicationData)

            # Email props
            w.page(CP_EMAIL)
            w.start(EM_Subject)
            w.write_str(str(subj))
            w.end()
            w.start(EM_From)
            w.write_str(str(from_))
            w.end()
            w.start(EM_To)
            w.write_str(str(to_))
            w.end()
            w.start(EM_DateReceived)
            w.write_str(when)
            w.end()
            # Include MessageClass like Z-Push
            w.start(EM_MessageClass)
            w.write_str("IPM.Note")
            w.end()
            # InternetCPID to signal UTF-8
            w.start(EM_InternetCPID)
            w.write_str("65001")
            w.end()
            w.start(EM_Read)
            w.write_str(read)
            w.end()

            # AirSyncBase <Body> (always include) with preference/truncation
            w.page(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            # ORDER MATTERS: Type -> EstimatedDataSize -> Truncated -> [Data OR Preview]
            w.start(ASB_Type)
            w.write_str(body_payload["type"])
            w.end()
            w.start(ASB_EstimatedDataSize)
            w.write_str(body_payload["estimated_size"])
            w.end()
            w.start(ASB_Truncated)
            w.write_str(body_payload["truncated"])
            w.end()

            # STANDARD TRUNCATION: Always send Data element with truncated HTML
            # This is how grommunio-sync and z-push work - no Preview element, no Truncated=2
            w.start(ASB_Data)
            if body_payload["type"] == "4" and "data_bytes" in body_payload:
                # Type=4 (MIME) uses OPAQUE bytes
                w.write_opaque(body_payload["data_bytes"])
            else:
                # Type=1/2 uses string data
                # DEBUG: Log what's being written to WBXML
                from app.diagnostic_logger import _write_json_line

                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "wbxml_body_data_write",
                        "body_type": body_payload["type"],
                        "data_length": (
                            len(body_payload["data"]) if body_payload.get("data") else 0
                        ),
                        "data_is_empty": not bool(body_payload.get("data")),
                        "data_preview": (
                            body_payload["data"][:100]
                            if body_payload.get("data")
                            else None
                        ),
                        "encoding": "opaque_utf8",
                    },
                )
                # CRITICAL iOS FIX: Type=1/2 MUST use OPAQUE (not STR_I) per iOS requirements
                w.write_opaque(body_payload["data"].encode("utf-8"))
            w.end()

            # DEBUG: Log body_payload details BEFORE Preview check
            from app.diagnostic_logger import _write_json_line

            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "body_payload_before_preview_check",
                    "has_data": bool(body_payload.get("data")),
                    "data_length": len(body_payload.get("data", "")),
                    "type_value": body_payload["type"],
                    "type_repr": repr(body_payload["type"]),
                    "type_in_tuple": body_payload["type"] in ("1", "2"),
                    "condition_result": bool(
                        body_payload.get("data") and body_payload["type"] in ("1", "2")
                    ),
                },
            )

            # CRITICAL FIX: NEVER send Preview when Data is present
            # Per MS-ASCMD §2.2.3.35.2: Preview is ONLY for when NO Data element is sent
            # If you're sending Data (truncated OR full), DO NOT send Preview
            # iOS Mail fails and requests full bodies when Preview is incorrectly included
            if False:  # DISABLED: Never send Preview when Data is present
                preview_text = body_payload["data"][:255]  # First 255 chars

                # DEBUG: Log Preview write attempt
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "wbxml_preview_write_attempt",
                        "preview_length": len(preview_text),
                        "preview_preview": preview_text[:50],
                        "body_type": body_payload["type"],
                        "is_truncated": body_payload.get("truncated"),
                    },
                )

                w.start(ASB_Preview)
                w.write_str(preview_text)
                w.end()

                # DEBUG: Confirm Preview written
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "wbxml_preview_written",
                        "preview_length": len(preview_text),
                    },
                )
            else:
                # DEBUG: Log why Preview was skipped
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "preview_skipped",
                        "reason": "truncated_or_no_data",
                        "has_data": bool(body_payload.get("data")),
                        "type_value": body_payload["type"],
                        "is_truncated": body_payload.get("truncated"),
                        "type_check": body_payload["type"] in ("1", "2"),
                    },
                )

            # REMOVED: ContentType must not be in Body (MS-ASAIRS: attachments only)
            w.end()  # </Body>
            # Native body type hint (as Z-Push does)
            w.page(CP_AIRSYNCBASE)
            w.start(ASB_NativeBodyType)
            w.write_str(body_payload["native_type"])
            w.end()

            # close ApplicationData, Add
            w.page(CP_AIRSYNC)
            w.end()  # </ApplicationData>
            w.end()  # </Add>

            count += 1

        w.end()  # </Commands>

    # Place MoreAvailable BEFORE Commands (grommunio/z-push behaviour)
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)

    # CRITICAL FIX: Must switch back to AirSync codepage after email body processing
    w.page(CP_AIRSYNC)

    w.end()  # </Collection>
    w.end()  # </Collections>
    w.end()  # </Sync>

    return SyncBatch(
        response_sync_key=new_sync_key,
        payload=w.bytes(),
        sent_count=count,
        total_available=len(items),
        more_available=more_available,
    )


def build_foldersync_with_folders(
    sync_key: str,
    folders: List[Dict[str, str]],
) -> bytes:
    """
    Build a FolderSync response with folder hierarchy for initial sync (SyncKey 0→1).

    Parameters
    ----------
    sync_key: str
        Server sync key to advertise in the response.
    folders: list[dict]
        Each dict should contain ``server_id`` / ``id``, ``display_name`` / ``name``,
        optional ``parent_id`` (defaults to "0"), and ``type`` (Folder class code, e.g. 2=Inbox).

    CRITICAL: Pass BASE tokens WITHOUT 0x40 bit - WBXMLWriter.start() adds it automatically!

    Base token values for FolderHierarchy codepage (0x07):
    - FolderSync = 0x16
    - Status = 0x0B
    - SyncKey = 0x12
    - Changes = 0x0E
    - Count = 0x07
    - Add = 0x0C
    - ServerId = 0x15
    - ParentId = 0x17
    - DisplayName = 0x08
    - Type = 0x0F
    """
    w = WBXMLWriter()
    w.header()

    # FolderHierarchy codepage (CP 7)
    CP_FOLDER = 0x07
    FH_FOLDERSYNC = 0x16
    FH_STATUS = 0x0C
    FH_SYNCKEY = 0x12
    FH_CHANGES = 0x0E
    FH_COUNT = 0x17
    FH_ADD = 0x0F
    FH_DISPLAYNAME = 0x07
    FH_SERVERID = 0x08
    FH_PARENTID = 0x09
    FH_TYPE = 0x0A
    FH_CLASS = 0x06  # CRITICAL: Outlook needs Class to know content type!

    w.page(CP_FOLDER)

    # <FolderSync>
    w.start(FH_FOLDERSYNC)

    # <Status>1</Status>
    w.start(FH_STATUS)
    w.write_str("1")
    w.end()

    # <SyncKey>1</SyncKey>
    w.start(FH_SYNCKEY)
    w.write_str(sync_key)
    w.end()

    # <Changes>
    w.start(FH_CHANGES)

    # <Count>N</Count>
    w.start(FH_COUNT)
    w.write_str(str(len(folders)))
    w.end()

    for folder in folders:
        server_id = folder.get("server_id") or folder.get("id") or ""
        display_name = folder.get("display_name") or folder.get("name") or ""
        folder_type = folder.get("type") or "2"
        parent_id = folder.get("parent_id") or "0"

        # Map folder type to class (CRITICAL for Outlook)
        # Types: 0=User, 2=Inbox, 3=Drafts, 4=Deleted, 5=Sent, 6=Outbox, 8=Calendar, 9=Contacts
        folder_class_map = {
            "0": "Email",  # Root/User folders default to Email
            "2": "Email",  # Inbox
            "3": "Email",  # Drafts
            "4": "Email",  # Deleted Items
            "5": "Email",  # Sent Items
            "6": "Email",  # Outbox
            "8": "Calendar",
            "9": "Contacts",
            "14": "Email",  # User-created email folders
        }
        folder_class = folder_class_map.get(str(folder_type), "Email")

        # <Add>
        w.start(FH_ADD)

        # <ServerId>
        w.start(FH_SERVERID)
        w.write_str(str(server_id))
        w.end()

        # <ParentId>
        if parent_id is not None:
            w.start(FH_PARENTID)
            w.write_str(str(parent_id))
            w.end()

        # <DisplayName>
        w.start(FH_DISPLAYNAME)
        w.write_str(display_name)
        w.end()

        # <Type>
        w.start(FH_TYPE)
        w.write_str(str(folder_type))
        w.end()

        w.end()  # </Add>
    w.end()  # </Changes>
    w.end()  # </FolderSync>

    return w.bytes()


def build_foldersync_no_changes(sync_key: str = "1", status: str = "1") -> bytes:
    """
    Minimal FolderSync 'no changes' WBXML using FolderHierarchy code page tokens
    aligned with Z-Push/Grommunio.
    """
    w = WBXMLWriter()
    w.header()

    CP_FOLDER = 0x07  # FolderHierarchy
    FH_FOLDERSYNC = 0x16
    FH_STATUS = 0x0C
    FH_SYNCKEY = 0x12
    FH_CHANGES = 0x0E
    FH_COUNT = 0x17

    w.page(CP_FOLDER)
    w.start(FH_FOLDERSYNC)
    w.start(FH_STATUS)
    w.write_str(status)
    w.end()
    w.start(FH_SYNCKEY)
    w.write_str(sync_key)
    w.end()
    w.start(FH_CHANGES)
    w.start(FH_COUNT)
    w.write_str("0")
    w.end()
    w.end()  # </Changes>
    w.end()  # </FolderSync>
    return w.bytes()


def build_provision_response(
    *,
    policy_key: str,
    include_policy_data: bool,
    provision_status: str = "1",
    policy_status: str = "1",
) -> bytes:
    """Build WBXML Provision response.

    When ``include_policy_data`` is True (phase 1), an ``EASProvisionDoc`` is emitted with
    a permissive policy document. For the final acknowledgement (phase 2) only
    the PolicyKey is returned.
    """
    w = WBXMLWriter()
    w.header()

    w.page(CP_PROVISION)
    w.start(PR_Provision)

    w.start(PR_Status)
    w.write_str(str(provision_status))
    w.end()

    w.start(PR_Policies)
    w.start(PR_Policy)

    w.start(PR_PolicyType)
    w.write_str("MS-EAS-Provisioning-WBXML")
    w.end()
    w.start(PR_Status)
    w.write_str(str(policy_status))
    w.end()
    w.start(PR_PolicyKey)
    w.write_str(policy_key)
    w.end()

    if include_policy_data:
        w.start(PR_Data)
        w.start(PR_EASProvisionDoc)

        # Minimal permissive policy compatible with iOS expectations
        policy_fields: List[tuple[int, str]] = [
            (PR_DevicePasswordEnabled, "0"),
            (PR_AlphanumericDevicePasswordRequired, "0"),
            (PR_PasswordRecoveryEnabled, "0"),
            (PR_AttachmentsEnabled, "1"),
            (PR_MinDevicePasswordLength, "0"),
            (PR_MaxInactivityTimeDeviceLock, "0"),
            (PR_MaxDevicePasswordFailedAttempts, "0"),
            (PR_MaxAttachmentSize, "52428800"),  # 50 MB
            (PR_AllowSimpleDevicePassword, "1"),
            (PR_DevicePasswordExpiration, "0"),
            (PR_DevicePasswordHistory, "0"),
            (PR_AllowStorageCard, "1"),
            (PR_AllowCamera, "1"),
            (PR_RequireDeviceEncryption, "0"),
            (PR_AllowUnsignedApplications, "1"),
            (PR_AllowUnsignedInstallationPackages, "1"),
            (PR_MinDevicePasswordComplexCharacters, "0"),
            (PR_AllowWiFi, "1"),
            (PR_AllowTextMessaging, "1"),
            (PR_AllowPOPIMAPEmail, "1"),
            (PR_AllowBluetooth, "2"),
            (PR_AllowIrDA, "1"),
            (PR_RequireManualSyncWhenRoaming, "0"),
            (PR_AllowDesktopSync, "1"),
            (PR_MaxCalendarAgeFilter, "0"),
            (PR_AllowHTMLEmail, "1"),
            (PR_MaxEmailAgeFilter, "0"),
            (PR_MaxEmailBodyTruncationSize, "-1"),
            (PR_MaxEmailHTMLBodyTruncationSize, "-1"),
            (PR_RequireSignedSMIMEMessages, "0"),
            (PR_RequireEncryptedSMIMEMessages, "0"),
            (PR_RequireSignedSMIMEAlgorithm, "0"),
            (PR_RequireEncryptionSMIMEAlgorithm, "0"),
            (PR_AllowSMIMEEncryptionAlgorithmNegotiation, "2"),
            (PR_AllowSMIMESoftCerts, "1"),
            (PR_AllowBrowser, "1"),
            (PR_AllowConsumerEmail, "1"),
            (PR_AllowRemoteDesktop, "1"),
            (PR_AllowInternetSharing, "1"),
        ]

        for token, value in policy_fields:
            w.start(token)
            w.write_str(value)
            w.end()

        w.end()  # </EASProvisionDoc>
        w.end()  # </Data>

    w.end()  # </Policy>
    w.end()  # </Policies>
    w.end()  # </Provision>

    return w.bytes()


def extract_synckey_and_collection(wb: bytes) -> tuple[Optional[str], Optional[str]]:
    """
    Very small reader:
    - Tracks current code page via SWITCH_PAGE.
    - When CP==AirSync and token==SyncKey/CollectionId, reads the following STR_I text.
    """
    cp = None
    i = 0
    sync_key = None
    coll_id = None

    def read_cstr(buf: bytes, pos: int) -> tuple[str, int]:
        j = pos
        while j < len(buf) and buf[j] != 0x00:
            j += 1
        s = buf[pos:j].decode("utf-8", errors="ignore")
        return s, j + 1

    while i < len(wb):
        b = wb[i]
        i += 1

        if b == SWITCH_PAGE:
            if i >= len(wb):
                break
            cp = wb[i]
            i += 1
            continue

        if b == STR_I:
            # skip inline string (we only read strings after known start tags)
            while i < len(wb) and wb[i] != 0x00:
                i += 1
            i += 1
            continue

        if b == END:
            continue

        # Tag start: content bit may be set (0x40)
        tok = b & 0x3F

        if cp == CP_AIRSYNC and tok in (AS_SyncKey, AS_CollectionId):
            # Next token must be STR_I
            # We skip any attributes/content flags—only STR_I matters to us.
            # Find the next STR_I:
            while i < len(wb) and wb[i] != STR_I:
                # allow nested tags; skip until we hit the inline string
                i += 1
            if i < len(wb) and wb[i] == STR_I:
                i += 1
                text, i = read_cstr(wb, i)
                if tok == AS_SyncKey:
                    sync_key = text
                else:
                    coll_id = text
            # eat until END of current element (best-effort)
            while i < len(wb) and wb[i] != END:
                i += 1
            if i < len(wb) and wb[i] == END:
                i += 1

        if sync_key and coll_id:
            break

    return sync_key, coll_id


# Legacy compatibility functions
def create_sync_response_wbxml(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    Legacy compatibility wrapper with Z-Push body preference support.

    Args:
        body_type_preference: 1=PlainText, 2=HTML (default), 3=RTF, 4=MIME
        truncation_size: Max body size in bytes (None = no truncation)
    """
    return build_sync_response(
        new_sync_key=sync_key,
        class_name=class_name,
        collection_id=collection_id,
        items=emails,
        window_size=window_size,
        more_available=more_available,
        body_type_preference=body_type_preference,
        truncation_size=truncation_size,
    )


def create_sync_response_wbxml_with_fetch(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    fetched: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
    body_type_preference: int = 2,
    truncation_size: Optional[int] = None,
) -> SyncBatch:
    """
    Build a Sync response containing <Collections>/<Collection> with optional <Commands>/<Add>
    and also <Responses>/<Fetch> bodies for items explicitly fetched by the client.
    """
    w = WBXMLWriter()
    w.header()

    # <Sync>
    w.cp(CP_AIRSYNC)
    w.start(AS_Sync)

    # CRITICAL: MS-ASCMD requires top-level Status BEFORE Collections!
    # <Status>1</Status>
    w.start(AS_Status)
    w.write_str("1")
    w.end()

    # <Collections><Collection>
    w.start(AS_Collections)
    w.start(AS_Collection)

    # CRITICAL FIX: Correct MS-ASCMD order - Status MUST come BEFORE Class!
    # Microsoft spec: SyncKey -> CollectionId -> Status -> Class
    w.start(AS_SyncKey)
    w.write_str(sync_key)
    w.end()
    w.start(AS_CollectionId)
    w.write_str(collection_id)
    w.end()
    w.start(AS_Status)
    w.write_str("1")
    w.end()
    w.start(AS_Class)
    w.write_str(class_name)
    w.end()

    # Commands for new items
    count = 0
    if emails:
        w.start(AS_Commands)
        for idx, em in enumerate(emails):
            if count >= window_size:
                break
            server_id = em.get("server_id") or f"{collection_id}:{em.get('id', idx+1)}"
            subj = str(em.get("subject") or "(no subject)")
            frm = str(em.get("from") or em.get("sender") or "")
            to = str(em.get("to") or em.get("recipient") or "")
            read = "1" if bool(em.get("is_read")) else "0"
            when = _ensure_utc_z(em.get("created_at"))
            # <Add>
            w.cp(CP_AIRSYNC)
            w.start(AS_Add)
            w.start(AS_ServerId)
            w.write_str(str(server_id))
            w.end()
            # DEBUG: log ServerId emitted in Add (with_fetch)
            try:
                from app.diagnostic_logger import _write_json_line as _dj

                _dj(
                    "activesync/activesync.log",
                    {
                        "event": "sync_add_server_id",
                        "server_id": str(server_id),
                        "email_id": em.get("id"),
                        "collection_id": collection_id,
                    },
                )
            except Exception:
                pass
            w.start(AS_ApplicationData)
            # Email props
            w.cp(CP_EMAIL)
            w.start(EM_Subject)
            w.write_str(subj)
            w.end()
            w.start(EM_From)
            w.write_str(frm)
            w.end()
            w.start(EM_To)
            w.write_str(to)
            w.end()
            w.start(EM_DateReceived)
            w.write_str(when)
            w.end()
            w.start(EM_MessageClass)
            w.write_str("IPM.Note")
            w.end()
            w.start(EM_InternetCPID)
            w.write_str("65001")
            w.end()
            w.start(EM_Read)
            w.write_str(read)
            w.end()
            # AirSyncBase Body — honor client BodyPreference and truncation
            w.cp(CP_AIRSYNCBASE)
            w.start(ASB_Body)
            body_payload = _prepare_body_payload(
                em,
                requested_type=body_type_preference,
                truncation_size=truncation_size,
            )
            w.start(ASB_Type)
            w.write_str(body_payload["type"])
            w.end()
            w.start(ASB_EstimatedDataSize)
            w.write_str(body_payload["estimated_size"])
            w.end()
            w.start(ASB_Truncated)
            w.write_str(body_payload["truncated"])
            w.end()

            # CRITICAL FIX: Preview-only mode for small truncations
            # Per MS-ASCMD §2.2.3.35.2: For initial sync (small truncation),
            # send ONLY Preview (plain text), NOT Data (HTML fragment)
            from app.diagnostic_logger import _write_json_line

            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "wbxml_preview_check_fetch",
                    "preview_only": body_payload.get("preview_only"),
                    "has_preview_text": bool(body_payload.get("preview_text")),
                    "preview_text_type": type(
                        body_payload.get("preview_text")
                    ).__name__,
                    "preview_text_len": len(body_payload.get("preview_text", "")),
                },
            )

            if body_payload.get("preview_only"):
                # Send ONLY Preview element for email list view
                preview_text = body_payload.get("preview_text", "")
                if preview_text:
                    try:
                        # Ensure preview is safe to write (ASCII-safe, no control chars)
                        # But allow UTF-8 multibyte characters (Hebrew, emoji, etc.)
                        safe_preview = preview_text[:255]  # MS-ASCMD limit

                        w.start(ASB_Preview)
                        w.write_str(safe_preview)
                        w.end()

                        _write_json_line(
                            "activesync/activesync.log",
                            {
                                "event": "wbxml_preview_only_mode_fetch",
                                "preview_length": len(safe_preview),
                                "truncation_mode": "preview_only",
                                "reason": "small_truncation_for_initial_sync",
                            },
                        )
                    except Exception as e:
                        _write_json_line(
                            "activesync/activesync.log",
                            {
                                "event": "wbxml_preview_write_error_fetch",
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "preview_length": len(preview_text),
                                "preview_sample": preview_text[:50],
                            },
                        )
                        raise
            else:
                # Normal mode: Send Data element
                w.start(ASB_Data)
                if body_payload["type"] == "4" and "data_bytes" in body_payload:
                    # Type=4 (MIME) uses OPAQUE bytes
                    w.write_opaque(body_payload["data_bytes"])
                else:
                    # Type=1/2 uses string data
                    # DEBUG: Log what's being written to WBXML
                    from app.diagnostic_logger import _write_json_line

                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "wbxml_body_data_write",
                        "body_type": body_payload["type"],
                        "data_length": (
                            len(body_payload["data"]) if body_payload.get("data") else 0
                        ),
                        "data_is_empty": not bool(body_payload.get("data")),
                        "data_preview": (
                            body_payload["data"][:100]
                            if body_payload.get("data")
                            else None
                        ),
                        "encoding": "opaque_utf8",
                    },
                )
                # CRITICAL iOS FIX: Type=1/2 MUST use OPAQUE (not STR_I) per iOS requirements
                w.write_opaque(body_payload["data"].encode("utf-8"))
            w.end()
            # REMOVED: ContentType must not be in Body (MS-ASAIRS: attachments only)
            w.end()  # </Body>
            w.cp(CP_AIRSYNCBASE)
            w.start(ASB_NativeBodyType)
            w.write_str(body_payload["native_type"])
            w.end()
            # Close appdata/add
            w.cp(CP_AIRSYNC)
            w.end()  # </ApplicationData>
            w.end()  # </Add>
            count += 1
        w.end()  # </Commands>

    # Place MoreAvailable BEFORE Commands (grommunio/z-push behaviour)
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)

    # CRITICAL FIX: Must switch back to AirSync codepage after email body processing
    w.page(CP_AIRSYNC)

    w.end()
    w.end()  # </Collection></Collections>
    w.end()  # </Sync>

    # CRITICAL FIX: Return SyncBatch object!
    return SyncBatch(
        response_sync_key=sync_key,
        payload=w.bytes(),
        sent_count=count,
        total_available=len(emails) + len(fetched),
        more_available=more_available,
    )


def build_settings_oof_get_response(oof_settings: Dict[str, Any]) -> bytes:
    """
    Build WBXML Settings:Oof:Get response.

    Based on MS-ASCMD § 2.2.3.119 (Settings:Oof) and Z-Push implementation.

    Args:
        oof_settings: Dictionary with OOF settings:
            - oof_state: 0=Disabled, 1=Enabled, 2=Scheduled
            - start_time: ISO datetime string (for state=2)
            - end_time: ISO datetime string (for state=2)
            - internal_message: Internal OOF message
            - internal_enabled: Boolean
            - external_message: External OOF message
            - external_enabled: Boolean
            - external_audience: 0=None, 1=Known, 2=All

    Returns:
        WBXML bytes for Settings response
    """
    w = WBXMLWriter()
    w.header()

    # <Settings>
    w.page(CP_SETTINGS)
    w.start(SETTINGS_Settings)

    # <Status>1</Status>
    w.start(SETTINGS_Status)
    w.write_str("1")  # Success
    w.end()

    # <Oof>
    w.start(SETTINGS_Oof)

    # <Get>
    w.start(SETTINGS_Get)

    # <OofState>
    w.start(SETTINGS_OofState)
    w.write_str(str(oof_settings.get("oof_state", 0)))
    w.end()

    # <StartTime> (only for state=2)
    if oof_settings.get("oof_state") == 2 and oof_settings.get("start_time"):
        w.start(SETTINGS_StartTime)
        w.write_str(_ensure_utc_z(oof_settings["start_time"]))
        w.end()

    # <EndTime> (only for state=2)
    if oof_settings.get("oof_state") == 2 and oof_settings.get("end_time"):
        w.start(SETTINGS_EndTime)
        w.write_str(_ensure_utc_z(oof_settings["end_time"]))
        w.end()

    # <OofMessage> for Internal
    if oof_settings.get("internal_enabled", True):
        w.start(SETTINGS_OofMessage)

        # <AppliesToInternal />
        w.start(SETTINGS_AppliesToInternal, with_content=False)

        # <Enabled>
        w.start(SETTINGS_Enabled)
        w.write_str("1" if oof_settings.get("internal_enabled", True) else "0")
        w.end()

        # <ReplyMessage>
        w.start(SETTINGS_ReplyMessage)
        w.write_str(oof_settings.get("internal_message", ""))
        w.end()

        # <BodyType>
        w.start(SETTINGS_BodyType)
        w.write_str("TEXT")  # or "HTML"
        w.end()

        w.end()  # </OofMessage>

    # <OofMessage> for External (if enabled)
    external_audience = oof_settings.get("external_audience", 0)
    if oof_settings.get("external_enabled", False) and external_audience > 0:
        w.start(SETTINGS_OofMessage)

        # <AppliesToExternalKnown /> or <AppliesToExternalUnknown />
        if external_audience == 1:  # Known contacts only
            w.start(SETTINGS_AppliesToExternalKnown, with_content=False)
        elif external_audience == 2:  # All external
            w.start(SETTINGS_AppliesToExternalUnknown, with_content=False)

        # <Enabled>
        w.start(SETTINGS_Enabled)
        w.write_str("1")
        w.end()

        # <ReplyMessage>
        w.start(SETTINGS_ReplyMessage)
        w.write_str(oof_settings.get("external_message", ""))
        w.end()

        # <BodyType>
        w.start(SETTINGS_BodyType)
        w.write_str("TEXT")
        w.end()

        w.end()  # </OofMessage>

    w.end()  # </Get>
    w.end()  # </Oof>
    w.end()  # </Settings>

    return w.bytes()


def build_settings_oof_set_response(status: int = 1) -> bytes:
    """
    Build WBXML Settings:Oof:Set response.

    Args:
        status: 1=Success, 2=Protocol error, 3=Access denied, etc.

    Returns:
        WBXML bytes for Settings response
    """
    w = WBXMLWriter()
    w.header()

    # <Settings>
    w.page(CP_SETTINGS)
    w.start(SETTINGS_Settings)

    # <Status>
    w.start(SETTINGS_Status)
    w.write_str(str(status))
    w.end()

    # <Oof>
    w.start(SETTINGS_Oof)

    # <Status>
    w.start(SETTINGS_Status)
    w.write_str(str(status))
    w.end()

    w.end()  # </Oof>
    w.end()  # </Settings>

    return w.bytes()


def create_invalid_synckey_response_wbxml(
    *, collection_id: str = "1", class_name: str = "Email"
) -> SyncBatch:
    """
    Build a minimal response that signals Status=3 (InvalidSyncKey) and forces the client to re-init
    the collection with SyncKey=0 (per MS-ASCMD).
    """
    w = WBXMLWriter()
    w.header()

    w.page(CP_AIRSYNC)
    w.start(AS_Sync)
    w.start(AS_Status)
    w.write_str("3")
    w.end()  # InvalidSyncKey
    w.start(AS_Collections)
    w.start(AS_Collection)
    w.start(AS_Class)
    w.write_str(class_name)
    w.end()
    w.start(AS_SyncKey)
    w.write_str("0")
    w.end()
    w.start(AS_CollectionId)
    w.write_str(collection_id)
    w.end()
    w.start(AS_Status)
    w.write_str("3")
    w.end()  # InvalidSyncKey
    w.end()
    w.end()
    w.end()

    payload = w.bytes()
    return SyncBatch(
        response_sync_key="0",
        payload=payload,
        sent_count=0,
        total_available=0,
        more_available=False,
    )


# Provision (CP 14)
PR_Provision = 0x05
PR_Policies = 0x06
PR_Policy = 0x07
PR_PolicyType = 0x08
PR_PolicyKey = 0x09
PR_Data = 0x0A
PR_Status = 0x0B
PR_RemoteWipe = 0x0C
PR_EASProvisionDoc = 0x0D
PR_DevicePasswordEnabled = 0x0E
PR_AlphanumericDevicePasswordRequired = 0x0F
PR_PasswordRecoveryEnabled = 0x11
PR_AttachmentsEnabled = 0x13
PR_MinDevicePasswordLength = 0x14
PR_MaxInactivityTimeDeviceLock = 0x15
PR_MaxDevicePasswordFailedAttempts = 0x16
PR_MaxAttachmentSize = 0x17
PR_AllowSimpleDevicePassword = 0x18
PR_DevicePasswordExpiration = 0x19
PR_DevicePasswordHistory = 0x1A
PR_AllowStorageCard = 0x1B
PR_AllowCamera = 0x1C
PR_RequireDeviceEncryption = 0x1D
PR_AllowUnsignedApplications = 0x1E
PR_AllowUnsignedInstallationPackages = 0x1F
PR_MinDevicePasswordComplexCharacters = 0x20
PR_AllowWiFi = 0x21
PR_AllowTextMessaging = 0x22
PR_AllowPOPIMAPEmail = 0x23
PR_AllowBluetooth = 0x24
PR_AllowIrDA = 0x25
PR_RequireManualSyncWhenRoaming = 0x26
PR_AllowDesktopSync = 0x27
PR_MaxCalendarAgeFilter = 0x28
PR_AllowHTMLEmail = 0x29
PR_MaxEmailAgeFilter = 0x2A
PR_MaxEmailBodyTruncationSize = 0x2B
PR_MaxEmailHTMLBodyTruncationSize = 0x2C
PR_RequireSignedSMIMEMessages = 0x2D
PR_RequireEncryptedSMIMEMessages = 0x2E
PR_RequireSignedSMIMEAlgorithm = 0x2F
PR_RequireEncryptionSMIMEAlgorithm = 0x30
PR_AllowSMIMEEncryptionAlgorithmNegotiation = 0x31
PR_AllowSMIMESoftCerts = 0x32
PR_AllowBrowser = 0x33
PR_AllowConsumerEmail = 0x34
PR_AllowRemoteDesktop = 0x35
PR_AllowInternetSharing = 0x36
PR_AccountOnlyRemoteWipe = 0x3B


def create_sync_response_wbxml_headers_only(
    *,
    sync_key: str,
    emails: List[Dict[str, Any]],
    collection_id: str = "1",
    window_size: int = 25,
    more_available: bool = False,
    class_name: str = "Email",
) -> SyncBatch:
    """Emit Adds without AirSyncBase:Body (header-only) for initial sync compatibility."""
    w = WBXMLWriter()
    w.header()

    w.page(CP_AIRSYNC)
    w.start(AS_Sync)
    w.start(AS_Status)
    w.write_str("1")
    w.end()

    w.start(AS_Collections)
    w.start(AS_Collection)
    w.start(AS_SyncKey)
    w.write_str(sync_key)
    w.end()
    w.start(AS_CollectionId)
    w.write_str(collection_id)
    w.end()
    w.start(AS_Status)
    w.write_str("1")
    w.end()
    w.start(AS_Class)
    w.write_str(class_name)
    w.end()

    count = 0
    if emails:
        w.start(AS_Commands)
        for idx, em in enumerate(emails):
            if count >= window_size:
                break
            server_id = em.get("server_id") or f"{collection_id}:{em.get('id', idx+1)}"
            subj = str(em.get("subject") or "(no subject)")
            frm = str(em.get("from") or em.get("sender") or "")
            to = str(em.get("to") or em.get("recipient") or "")
            read = "1" if bool(em.get("is_read")) else "0"
            when = _ensure_utc_z(em.get("created_at"))

            w.cp(CP_AIRSYNC)
            w.start(AS_Add)
            w.start(AS_ServerId)
            w.write_str(server_id)
            w.end()
            try:
                from app.diagnostic_logger import _write_json_line as _dj

                _dj(
                    "activesync/activesync.log",
                    {
                        "event": "sync_add_server_id",
                        "server_id": server_id,
                        "email_id": em.get("id"),
                        "collection_id": collection_id,
                    },
                )
            except Exception:
                pass

            w.start(AS_ApplicationData)
            w.cp(CP_EMAIL)
            w.start(EM_Subject)
            w.write_str(subj)
            w.end()
            if frm:
                w.start(EM_From)
                w.write_str(frm)
                w.end()
            if to:
                w.start(EM_To)
                w.write_str(to)
                w.end()
            if when:
                w.start(EM_DateReceived)
                w.write_str(when)
                w.end()
            w.start(EM_MessageClass)
            w.write_str("IPM.Note")
            w.end()
            w.start(EM_InternetCPID)
            w.write_str("65001")
            w.end()
            w.start(EM_Read)
            w.write_str(read)
            w.end()
            w.cp(CP_AIRSYNC)
            w.end()  # </ApplicationData>
            w.end()  # </Add>
            count += 1
        w.end()  # </Commands>

    # Place MoreAvailable BEFORE Commands (grommunio/z-push behaviour)
    if more_available:
        w.start(AS_MoreAvailable, with_content=False)

    w.page(CP_AIRSYNC)
    w.end()
    w.end()
    w.end()

    return SyncBatch(
        response_sync_key=sync_key,
        payload=w.bytes(),
        sent_count=count,
        total_available=len(emails),
        more_available=more_available,
    )
