#!/usr/bin/env python3
"""Decode the full WBXML from line 240 to find the issue"""

# First 100 bytes of the WBXML from line 240
wbxml_hex = (
    "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000114"
    + "56474d03313a323700015d000254034677643a20d794d790d79d20d790d7aad79d20d79ed798d7a4"
)

wbxml_bytes = bytes.fromhex(wbxml_hex)

# Correct token definitions from wbxml_builder.py
tokens = {
    0x00: "NULL/END",
    0x01: "END",
    0x03: "STR_I",
    0x0B: "SyncKey",
    0x0D: "ServerId",
    0x0E: "Status",
    0x0F: "Collection",
    0x10: "Class",
    0x12: "CollectionId",
    0x14: "MoreAvailable",
    0x16: "Commands",
    0x1C: "Collections",
    0x1D: "ApplicationData",
    0x07: "Add",
    0x45: "SWITCH_PAGE",
}

print("Full WBXML Decode (First 100 bytes):")
print("=" * 60)

pos = 0
indent = 0

while pos < len(wbxml_bytes) and pos < 100:
    b = wbxml_bytes[pos]

    if b == 0x03:  # STR_I
        start = pos + 1
        end = start
        while end < len(wbxml_bytes) and wbxml_bytes[end] != 0x00:
            end += 1
        string_val = wbxml_bytes[start:end].decode("utf-8", errors="ignore")
        print(
            f"{'  ' * indent}[{pos:03d}] 0x03 STR_I: '{string_val[:20]}{'...' if len(string_val) > 20 else ''}'"
        )
        pos = end
    elif b == 0x01:
        indent = max(0, indent - 1)
        print(f"{'  ' * indent}[{pos:03d}] 0x01 </END>")
    elif b == 0x00:
        print(f"{'  ' * indent}[{pos:03d}] 0x00 NULL")
    else:
        # Check if tag has content (bit 0x40)
        tag_byte = b & 0x3F
        has_content = (b & 0x40) != 0

        tag_name = tokens.get(tag_byte, tokens.get(b, f"UNKNOWN_0x{b:02X}"))
        content_flag = " +content" if has_content else ""

        print(f"{'  ' * indent}[{pos:03d}] 0x{b:02X} <{tag_name}>{content_flag}")

        if b not in [0x01, 0x00] and has_content:
            indent += 1

    pos += 1

print("")
print("=" * 60)
print("KEY FINDING:")
print("─" * 60)

# Check the exact byte positions
sync_pos = wbxml_hex.find("4b")  # SyncKey token (0x0B + 0x40)
coll_pos = wbxml_hex.find("52")  # CollectionId token (0x12 + 0x40)
status_pos = wbxml_hex.find("4e")  # Status token (0x0E + 0x40)
class_pos = wbxml_hex.find("50")  # Class token (0x10 + 0x40)
more_pos = wbxml_hex.find("14")  # MoreAvailable token
cmd_pos = wbxml_hex.find("56")  # Commands token (0x16 + 0x40)

print(f"Element positions (hex offset):")
print(f"  SyncKey:      0x{sync_pos:02x}")
print(f"  CollectionId: 0x{coll_pos:02x}")
print(f"  Status:       0x{status_pos:02x}")
print(f"  Class:        0x{class_pos:02x}")
print(f"  MoreAvailable: 0x{more_pos:02x} ← CRITICAL")
print(f"  Commands:     0x{cmd_pos:02x}")
print("")

if class_pos < more_pos < cmd_pos:
    print("✅ Element order is CORRECT:")
    print("   Class → MoreAvailable → Commands")
else:
    print("❌ Element order is WRONG!")
