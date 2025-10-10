#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
settings_parser.py — Parse ActiveSync Settings:Oof WBXML requests.

Based on Microsoft MS-ASCMD § 2.2.3.119 (Settings) and Z-Push/Grommunio implementation.
"""

from typing import Any, Dict

from .wbxml_builder import (
    CP_SETTINGS,
    END,
    SETTINGS_IMEI,
    SETTINGS_OS,
    STR_I,
    SWITCH_PAGE,
    SETTINGS_AppliesToExternalKnown,
    SETTINGS_AppliesToExternalUnknown,
    SETTINGS_AppliesToInternal,
    SETTINGS_BodyType,
    SETTINGS_DeviceInformation,
    SETTINGS_Enabled,
    SETTINGS_EndTime,
    SETTINGS_FriendlyName,
    SETTINGS_Get,
    SETTINGS_Model,
    SETTINGS_Oof,
    SETTINGS_OofMessage,
    SETTINGS_OofState,
    SETTINGS_OSLanguage,
    SETTINGS_PhoneNumber,
    SETTINGS_ReplyMessage,
    SETTINGS_Set,
    SETTINGS_Settings,
    SETTINGS_StartTime,
    SETTINGS_UserAgent,
)


def _read_inline_string(data: bytes, i: int) -> tuple[str, int]:
    """Read WBXML STR_I inline string."""
    if i >= len(data) or data[i] != STR_I:
        return "", i
    i += 1
    start = i
    while i < len(data) and data[i] != 0x00:
        i += 1
    text = data[start:i].decode("utf-8", errors="replace")
    if i < len(data) and data[i] == 0x00:
        i += 1
    return text, i


def parse_settings_request(data: bytes) -> Dict[str, Any]:
    """
    Parse ActiveSync Settings WBXML request.

    Supports:
    - Settings:Oof:Get
    - Settings:Oof:Set
    - Settings:DeviceInformation:Set

    Args:
        data: Raw WBXML request bytes

    Returns:
        Dictionary with parsed settings:
        {
            "action": "oof_get" | "oof_set" | "device_info_set",
            "oof": {
                "oof_state": int,
                "start_time": str,
                "end_time": str,
                "internal_message": str,
                "internal_enabled": bool,
                "external_message": str,
                "external_enabled": bool,
                "external_audience": int,
            },
            "device_info": {
                "model": str,
                "imei": str,
                "friendly_name": str,
                "os": str,
                "os_language": str,
                "phone_number": str,
                "user_agent": str,
            }
        }
    """
    result = {
        "action": None,
        "oof": {},
        "device_info": {},
    }

    if not data or len(data) < 4:
        return result

    # Skip WBXML header (4 bytes: version, public ID, charset, string table)
    i = 4

    cp = 0  # Current codepage
    stack = []  # Tag stack for tracking nesting
    current_oof_message = None  # Track current OofMessage being parsed

    while i < len(data):
        b = data[i]
        i += 1

        # Handle control bytes
        if b == SWITCH_PAGE:
            if i < len(data):
                cp = data[i]
                i += 1
            continue

        if b == END:
            if stack:
                popped = stack.pop()
                # If we're closing an OofMessage, reset tracking
                if popped == "OofMessage":
                    current_oof_message = None
            continue

        # Extract token and content flag
        has_content = bool(b & 0x40)
        token = b & 0x3F

        # Settings codepage parsing
        if cp == CP_SETTINGS:
            if token == SETTINGS_Settings:
                stack.append("Settings")
                continue

            if token == SETTINGS_Oof:
                stack.append("Oof")
                continue

            if token == SETTINGS_Get and "Oof" in stack:
                result["action"] = "oof_get"
                stack.append("Get")
                continue

            if token == SETTINGS_Set and "Oof" in stack:
                result["action"] = "oof_set"
                stack.append("Set")
                continue

            if token == SETTINGS_OofState and has_content:
                text, i = _read_inline_string(data, i)
                try:
                    result["oof"]["oof_state"] = int(text)
                except ValueError:
                    result["oof"]["oof_state"] = 0
                continue

            if token == SETTINGS_StartTime and has_content:
                text, i = _read_inline_string(data, i)
                result["oof"]["start_time"] = text
                continue

            if token == SETTINGS_EndTime and has_content:
                text, i = _read_inline_string(data, i)
                result["oof"]["end_time"] = text
                continue

            if token == SETTINGS_OofMessage:
                stack.append("OofMessage")
                current_oof_message = {}
                continue

            if token == SETTINGS_AppliesToInternal:
                if current_oof_message is not None:
                    current_oof_message["applies_to"] = "internal"
                continue

            if token == SETTINGS_AppliesToExternalKnown:
                if current_oof_message is not None:
                    current_oof_message["applies_to"] = "external_known"
                    result["oof"]["external_audience"] = 1
                continue

            if token == SETTINGS_AppliesToExternalUnknown:
                if current_oof_message is not None:
                    current_oof_message["applies_to"] = "external_unknown"
                    result["oof"]["external_audience"] = 2
                continue

            if token == SETTINGS_Enabled and has_content:
                text, i = _read_inline_string(data, i)
                enabled = text.strip() == "1"
                if current_oof_message is not None:
                    current_oof_message["enabled"] = enabled
                    # Apply to result based on message type
                    applies_to = current_oof_message.get("applies_to")
                    if applies_to == "internal":
                        result["oof"]["internal_enabled"] = enabled
                    elif applies_to in ("external_known", "external_unknown"):
                        result["oof"]["external_enabled"] = enabled
                continue

            if token == SETTINGS_ReplyMessage and has_content:
                text, i = _read_inline_string(data, i)
                if current_oof_message is not None:
                    current_oof_message["message"] = text
                    # Apply to result based on message type
                    applies_to = current_oof_message.get("applies_to")
                    if applies_to == "internal":
                        result["oof"]["internal_message"] = text
                    elif applies_to in ("external_known", "external_unknown"):
                        result["oof"]["external_message"] = text
                continue

            if token == SETTINGS_BodyType and has_content:
                text, i = _read_inline_string(data, i)
                if current_oof_message is not None:
                    current_oof_message["body_type"] = text
                continue

            # DeviceInformation parsing
            if token == SETTINGS_DeviceInformation:
                stack.append("DeviceInformation")
                result["action"] = "device_info_set"
                continue

            if token == SETTINGS_Model and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["model"] = text
                continue

            if token == SETTINGS_IMEI and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["imei"] = text
                continue

            if token == SETTINGS_FriendlyName and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["friendly_name"] = text
                continue

            if token == SETTINGS_OS and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["os"] = text
                continue

            if token == SETTINGS_OSLanguage and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["os_language"] = text
                continue

            if token == SETTINGS_PhoneNumber and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["phone_number"] = text
                continue

            if token == SETTINGS_UserAgent and has_content:
                text, i = _read_inline_string(data, i)
                result["device_info"]["user_agent"] = text
                continue

        # Skip unknown tokens with inline strings
        if has_content and i < len(data) and data[i] == STR_I:
            _, i = _read_inline_string(data, i)

    return result
