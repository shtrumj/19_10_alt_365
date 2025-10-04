#!/usr/bin/env python3
"""
Decode WBXML Sync response to understand exact structure
"""

import sys

# AirSync codepage 0 tokens
AIRSYNC_TOKENS = {
    0x05: "Sync",
    0x0C: "Status", 
    0x0D: "Collection",
    0x0E: "ServerId",  # Different than we thought!
    0x0F: "Add",
    0x11: "CollectionId",
    0x12: "Commands",
    0x14: "Class",
    0x15: "MoreAvailable",
    0x18: "GetChanges",
    0x1F: "WindowSize",
    0x20: "SyncKey",
}

# Email2 codepage 2 tokens
EMAIL2_TOKENS = {
    0x06: "To",
    0x07: "DateReceived",
    0x09: "Importance",
    0x0B: "Read",
    0x13: "From",
    0x15: "Subject",
}

# AirSyncBase codepage 17 tokens
AIRSYNCBASE_TOKENS = {
    0x05: "Body",
    0x06: "Data",
    0x07: "EstimatedDataSize",
    0x08: "Truncated",
    0x0A: "Type",
}

# FolderHierarchy codepage 7 tokens (for comparison)
FOLDERHIERARCHY_TOKENS = {
    0x05: "FolderSync",
    0x06: "Status",
    0x07: "SyncKey",
    0x08: "Changes",
    0x09: "Count",
    0x0A: "Add",
    0x0B: "ServerId",
    0x0C: "ParentId",
    0x0D: "DisplayName",
    0x0E: "Type",
}

def decode_wbxml(data: bytes) -> str:
    """Decode WBXML and return human-readable structure"""
    output = []
    indent = 0
    i = 0
    current_codepage = 0
    codepage_map = {0: AIRSYNC_TOKENS, 2: EMAIL2_TOKENS, 7: FOLDERHIERARCHY_TOKENS, 17: AIRSYNCBASE_TOKENS}
    
    # Parse header
    if len(data) < 6:
        return "ERROR: Data too short"
    
    output.append(f"=== WBXML HEADER ===")
    output.append(f"Version: 0x{data[0]:02x}")
    output.append(f"PublicID: 0x{data[1]:02x}")
    output.append(f"Charset: 0x{data[2]:02x}")
    output.append(f"StringTable: 0x{data[3]:02x}")
    output.append(f"")
    output.append(f"=== BODY ===")
    
    i = 4
    while i < len(data):
        byte = data[i]
        
        if byte == 0x00:  # SWITCH_PAGE
            i += 1
            if i < len(data):
                current_codepage = data[i]
                codepage_name = {0: "AirSync", 2: "Email2", 7: "FolderHierarchy", 17: "AirSyncBase"}.get(current_codepage, f"Unknown({current_codepage})")
                output.append(f"{'  ' * indent}[SWITCH to codepage {current_codepage} - {codepage_name}]")
            i += 1
            continue
            
        if byte == 0x01:  # END
            indent -= 1
            output.append(f"{'  ' * indent}</END>")
            i += 1
            continue
            
        if byte == 0x03:  # STR_I
            i += 1
            string_bytes = []
            while i < len(data) and data[i] != 0x00:
                string_bytes.append(data[i])
                i += 1
            try:
                string_value = bytes(string_bytes).decode('utf-8')
            except:
                string_value = f"<binary: {bytes(string_bytes).hex()}>"
            output.append(f"{'  ' * indent}  STR_I: \"{string_value}\"")
            i += 1  # Skip null terminator
            continue
        
        # Check if it's a tag
        has_content = (byte & 0x40) != 0
        token_value = byte & 0x3F
        
        tokens = codepage_map.get(current_codepage, {})
        tag_name = tokens.get(token_value, f"UNKNOWN_0x{token_value:02x}")
        
        if has_content:
            output.append(f"{'  ' * indent}<{tag_name}> (0x{byte:02x})")
            indent += 1
        else:
            output.append(f"{'  ' * indent}<{tag_name}/> (0x{byte:02x} - EMPTY TAG)")
        
        i += 1
    
    return "\n".join(output)

if __name__ == "__main__":
    # Test with our current WBXML
    test_hex = "03016a0000004e4c033100016003310001584d5403456d61696c00015103310001600331000104c033100011805f03310001524f5a03313a333500014803000002530373687472756d6a40676d61696c2e636f6d0001460379"
    
    print("=" * 80)
    print("DECODING OUR CURRENT SYNC WBXML")
    print("=" * 80)
    print()
    
    test_bytes = bytes.fromhex(test_hex)
    decoded = decode_wbxml(test_bytes)
    print(decoded)
    print()
    print("=" * 80)
    print(f"Total length: {len(test_bytes)} bytes")
    print("=" * 80)

