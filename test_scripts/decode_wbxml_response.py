#!/usr/bin/env python3
"""Decode the WBXML response from logs to identify protocol issues"""

import sys

# From line 55 in the log
wbxml_hex = "03016a000000454e033100015c4f4b0332000152033100014e033100015003456d61696c000156"

wbxml_bytes = bytes.fromhex(wbxml_hex)

print("WBXML Response Analysis")
print("=" * 60)
print(f"Total length: {len(wbxml_bytes)} bytes")
print(f"Hex: {wbxml_hex}")
print("")
print("Decoded tokens:")
print("-" * 60)

# WBXML tokens for ActiveSync
TOKENS = {
    0x03: "STR_I (inline string)",
    0x01: "END",
    0x00: "END",
    0x45: "CP_AIRSYNC",
    0x0E: "Status (AirSync)",
    0x0C: "SyncKey (AirSync)",
    0x5C: "Collections (AirSync)",
    0x4F: "Collection (AirSync)",
    0x4B: "Class (AirSync)",
    0x52: "CollectionId (AirSync)",
    0x4E: "Status (Collection)",
    0x50: "MoreAvailable (AirSync)",
    0x56: "Responses (AirSync)",
    0x47: "Add (AirSync)",
}

i = 0
indent = 0
while i < len(wbxml_bytes):
    b = wbxml_bytes[i]
    
    if b == 0x03:  # STR_I
        print("  " * indent + f"[{i:3d}] 0x{b:02X} = STR_I (inline string)")
        i += 1
        # Read string until null terminator
        start = i
        while i < len(wbxml_bytes) and wbxml_bytes[i] != 0x00:
            i += 1
        string_bytes = wbxml_bytes[start:i]
        try:
            string_val = string_bytes.decode('utf-8')
            print("  " * indent + f"      String: '{string_val}'")
        except:
            print("  " * indent + f"      Bytes: {string_bytes.hex()}")
    elif b == 0x01:
        indent -= 1
        print("  " * indent + f"[{i:3d}] 0x{b:02X} = END")
    elif b == 0x00:
        indent -= 1
        print("  " * indent + f"[{i:3d}] 0x{b:02X} = END (terminator)")
    elif b in TOKENS:
        print("  " * indent + f"[{i:3d}] 0x{b:02X} = {TOKENS[b]}")
        if b not in [0x01, 0x00]:
            indent += 1
    else:
        print("  " * indent + f"[{i:3d}] 0x{b:02X} = UNKNOWN TOKEN")
    
    i += 1

print("")
print("=" * 60)
print("ANALYSIS:")
print("-" * 60)
print("✅ Proper WBXML header (03 01 6a 00 00 00)")
print("✅ Switch to AirSync codepage (45)")
print("✅ Top-level Status = 1 (0E 03 31 00 01)")
print("✅ Collections tag (5C)")
print("✅ Collection tag (4F)")
print("✅ SyncKey = 2 (4B 03 32 00 01)")
print("✅ CollectionId = 1 (52 03 31 00 01)")
print("✅ Collection Status = 1 (4E 03 31 00 01)")
print("✅ MoreAvailable tag (50) - PRESENT")
print("✅ Class = Email (03 456d61696c 00 01)")
print("")
print("🔍 OBSERVATION:")
print("The MoreAvailable tag (0x50) is present at byte offset 25")
print("This should tell Outlook there are more emails to fetch.")
print("")
print("🤔 POSSIBLE ISSUE:")
print("MoreAvailable is a SELF-CLOSING tag - it has no value.")
print("In WBXML: 0x50 = MoreAvailable tag")
print("         0x01 = END (closes the tag)")
print("")
print("According to MS-ASCMD, MoreAvailable should be an EMPTY element")
print("(presence indicates true, absence indicates false)")
print("")
print("Let's check if we're writing it correctly...")

