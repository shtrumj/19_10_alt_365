#!/usr/bin/env python3
"""
iPhone-specific WBXML encoder
Matches the iPhone's non-standard WBXML format
"""

import io

def create_iphone_foldersync_wbxml(sync_key: str = "1") -> bytes:
    """
    Create iPhone-compatible WBXML FolderSync response
    Matches the iPhone's specific WBXML encoding format
    """
    output = io.BytesIO()
    
    # iPhone WBXML Header (match exactly)
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00\x00\x07')  # String table length 7 (match iPhone)
    
    # iPhone uses a different namespace encoding
    # Instead of SWITCH_PAGE (0x00), it uses direct namespace encoding
    # Based on iPhone's pattern: 56520330000101
    
    # Try to match iPhone's namespace pattern
    # The iPhone sends: 56520330000101
    # Let's try to reverse-engineer this pattern
    
    # Start with the iPhone's pattern but adapt for response
    output.write(b'\x56\x52')  # Match iPhone's namespace prefix
    output.write(b'\x03')      # STR_I
    output.write(b'0')         # Status value
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    # SyncKey
    output.write(b'\x47')      # SyncKey tag
    output.write(b'\x03')      # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    # Changes
    output.write(b'\x48')      # Changes tag
    output.write(b'\x49')      # Count tag
    output.write(b'\x03')      # STR_I
    output.write(b'1')          # Count = 1
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    # Add folder
    output.write(b'\x4A')      # Add tag
    output.write(b'\x4B')      # ServerId tag
    output.write(b'\x03')      # STR_I
    output.write(b'1')          # ServerId
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    output.write(b'\x4C')      # ParentId tag
    output.write(b'\x03')      # STR_I
    output.write(b'0')          # ParentId
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    output.write(b'\x4D')      # DisplayName tag
    output.write(b'\x03')      # STR_I
    output.write(b'Inbox')     # DisplayName
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    output.write(b'\x4E')      # Type tag
    output.write(b'\x03')      # STR_I
    output.write(b'2')          # Type (Inbox)
    output.write(b'\x00')      # String terminator
    output.write(b'\x01')      # END tag
    
    # End Add
    output.write(b'\x01')      # END tag
    
    # End Changes
    output.write(b'\x01')      # END tag
    
    # End FolderSync
    output.write(b'\x01')      # END tag
    
    return output.getvalue()

if __name__ == "__main__":
    wbxml = create_iphone_foldersync_wbxml()
    print(f"iPhone-compatible WBXML length: {len(wbxml)}")
    print(f"iPhone-compatible WBXML hex: {wbxml.hex()}")
