#!/usr/bin/env python3
"""Decode WBXML using ACTUAL token values from wbxml_builder.py"""

# From line 190 in activesync.log
wbxml_hex = (
    "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000156"
)
wbxml_bytes = bytes.fromhex(wbxml_hex)

# Actual tokens from activesync/wbxml_builder.py
CP_AIRSYNC = 0x00
CP_AIRSYNCBASE = 0x11

# AirSync codepage (0x00)
AS_Sync = 0x56
AS_Responses = 0x56  # Same as Sync in some contexts
AS_Add = 0x47
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
AS_Options = 0x17
AS_FilterType = 0x18
AS_Truncation = 0x19
AS_RtfTruncation = 0x1A
AS_Conflict = 0x1B
AS_Collections = 0x1C
AS_ApplicationData = 0x1D
AS_DeletesAsMoves = 0x1E
AS_NotifyGUID = 0x1F
AS_Supported = 0x20
AS_SoftDelete = 0x21
AS_MIMESupport = 0x22
AS_MIMETruncation = 0x23
AS_Wait = 0x24
AS_Limit = 0x25
AS_Partial = 0x26
AS_ConversationMode = 0x27
AS_MaxItems = 0x28
AS_HeartbeatInterval = 0x29

tokens = {
    # Control tokens
    0x00: "END/NULL",
    0x01: "END",
    0x03: "STR_I",
    0x45: "SWITCH_PAGE(AIRSYNC)",
    # AirSync tokens (page 0x00)
    0x56: "Sync",
    0x47: "Add",
    0x0B: "SyncKey",
    0x0C: "ClientId",
    0x0D: "ServerId",
    0x0E: "Status",
    0x0F: "Collection",
    0x10: "Class",
    0x12: "CollectionId",
    0x13: "GetChanges",
    0x14: "MoreAvailable",
    0x15: "WindowSize",
    0x16: "Commands",
    0x17: "Options",
    0x1C: "Collections",
    0x1D: "ApplicationData",
}

print("WBXML Hex:", wbxml_hex)
print("")
print("Decoded Structure:")
print("=" * 60)

pos = 0
indent = 0

while pos < len(wbxml_bytes) and pos < 50:
    b = wbxml_bytes[pos]

    if b == 0x03:  # STR_I
        start = pos + 1
        end = start
        while end < len(wbxml_bytes) and wbxml_bytes[end] != 0x00:
            end += 1
        string_val = wbxml_bytes[start:end].decode("utf-8", errors="ignore")
        print(f"{'  ' * indent}[{pos:02d}] STR_I: '{string_val}'")
        pos = end
    elif b == 0x01:
        indent = max(0, indent - 1)
        print(f"{'  ' * indent}[{pos:02d}] END")
    elif b == 0x00:
        print(f"{'  ' * indent}[{pos:02d}] NULL/END")
    else:
        # Check if tag has content (bit 0x40)
        tag_byte = b & 0x3F  # Remove content flag
        has_content = (b & 0x40) != 0

        if tag_byte in tokens or b in tokens:
            tag_name = tokens.get(tag_byte, tokens.get(b, f"UNKNOWN_0x{b:02X}"))
            content_flag = " [with_content]" if has_content else ""
            print(f"{'  ' * indent}[{pos:02d}] 0x{b:02X} <{tag_name}>{content_flag}")
            if b not in [0x01, 0x00]:
                indent += 1
        else:
            print(f"{'  ' * indent}[{pos:02d}] 0x{b:02X} UNKNOWN")

    pos += 1

print("")
print("=" * 60)
print("CRITICAL ANALYSIS:")
print("─" * 60)

# Check if MoreAvailable (0x14) appears BEFORE Commands (0x16)
more_idx = wbxml_hex.find("14")
cmd_idx = wbxml_hex.find("16")

if more_idx >= 0 and cmd_idx >= 0:
    if more_idx < cmd_idx:
        print(
            f"✅ MoreAvailable (pos {more_idx//2}) BEFORE Commands (pos {cmd_idx//2})"
        )
    else:
        print(f"❌ MoreAvailable (pos {more_idx//2}) AFTER Commands (pos {cmd_idx//2})")
elif more_idx < 0:
    print(f"❌ MoreAvailable (0x14) NOT FOUND in response!")
elif cmd_idx < 0:
    print(f"⚠️  Commands (0x16) NOT FOUND (might be later in response)")
