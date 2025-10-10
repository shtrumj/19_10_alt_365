#!/usr/bin/env python3
"""Decode the actual WBXML response from the log to check MoreAvailable position"""

# From line 109 in the log - the FIRST 100 bytes of the response
wbxml_hex_start = (
    "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000156"
)

# Decode to see the structure
wbxml_bytes = bytes.fromhex(wbxml_hex_start)

print("WBXML Structure Analysis (First 40 bytes)")
print("=" * 60)

# MS-ASCMD tokens
tokens = {
    0x05: "Add",
    0x0C: "SyncKey",
    0x0D: "ClientId",
    0x0E: "ServerId",
    0x0F: "Status",
    0x12: "Collection",
    0x13: "Class",
    0x14: "MoreAvailable",
    0x15: "Commands",
    0x16: "Responses",
    0x4E: "Status (top)",
    0x45: "CP_AIRSYNC",
    0x4F: "Collection",
    0x50: "MoreAvailable (wrong token?)",
    0x52: "CollectionId",
    0x56: "Responses",
    0x5C: "Collections",
    0x47: "Add",
    0x4B: "Class",
}

pos = 0
indent = 0

print(f"Hex: {wbxml_hex_start}")
print("")

while pos < len(wbxml_bytes) and pos < 40:
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
        print(f"{'  ' * indent}[{pos:02d}] NULL")
    elif b in tokens:
        print(f"{'  ' * indent}[{pos:02d}] 0x{b:02X} = {tokens[b]}")
        if b not in [0x01, 0x00]:
            indent += 1
    else:
        print(f"{'  ' * indent}[{pos:02d}] 0x{b:02X}")

    pos += 1

print("")
print("=" * 60)
print("CRITICAL CHECK:")
print("─" * 60)
print("Expected order (Z-Push/MS-ASCMD):")
print("  <Collection>")
print("    <SyncKey>2</SyncKey>")
print("    <CollectionId>1</CollectionId>")
print("    <Status>1</Status>")
print("    <MoreAvailable/>  ← MUST be BEFORE Commands!")
print("    <Commands>")
print("      <Add>...</Add>")
print("    </Commands>")
print("  </Collection>")
print("")
print("Our order:")
wbxml_str = wbxml_hex_start
if "4b" in wbxml_str.lower():  # Class (0x4B)
    class_pos = wbxml_str.lower().index("4b")
    print(f"  Class at position {class_pos // 2}")
if "56" in wbxml_str.lower():  # Responses (0x56)
    resp_pos = wbxml_str.lower().index("56")
    print(f"  Responses at position {resp_pos // 2}")
if "14" in wbxml_str.lower():  # MoreAvailable (0x14)
    more_pos = wbxml_str.lower().index("14")
    print(f"  MoreAvailable (0x14) - NOT FOUND in first 40 bytes!")
    print(f"  ❌ This means MoreAvailable comes AFTER Commands!")
else:
    print(f"  ❌ MoreAvailable (0x14) not in first 40 bytes")
    print(f"  ❌ It's probably at the END, which is WRONG!")
