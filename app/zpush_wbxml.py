#!/usr/bin/env python3
"""
Z-Push-style WBXML FolderSync response for iPhone compatibility
Based on Z-Push's proven implementation standards
"""

import io

def create_zpush_style_foldersync_wbxml(sync_key: str = "1") -> bytes:
    """
    Create Z-Push-style minimal WBXML FolderSync response
    Based on Z-Push's 10 years of successful ActiveSync implementation
    """
    output = io.BytesIO()
    
    # Z-Push WBXML Header (match iPhone's request format)
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00\x00\x07')  # String table length 7 (match iPhone request)
    
    # Switch to FolderHierarchy namespace (Z-Push standard)
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x01')  # Codepage 1 (FolderHierarchy)
    
    # FolderSync with Z-Push structure
    output.write(b'\x45')  # FolderSync start tag (0x05 + content flag)
    output.write(b'\x46')  # Status tag (0x06 + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'1')     # Status value (success)
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # SyncKey (Z-Push standard)
    output.write(b'\x47')  # SyncKey tag (0x07 + content flag)
    output.write(b'\x03')  # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Changes with Z-Push minimal approach
    output.write(b'\x48')  # Changes tag (0x08 + content flag)
    output.write(b'\x49')  # Count tag (0x09 + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'1')     # Count = 1 (only Inbox for iPhone compatibility)
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Single Inbox folder (Z-Push minimal approach for iPhone)
    output.write(b'\x4A')  # Add tag (0x0A + content flag)
    
    # ServerId
    output.write(b'\x4B')  # ServerId tag (0x0B + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'1')     # ServerId
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # ParentId
    output.write(b'\x4C')  # ParentId tag (0x0C + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'0')     # ParentId (root)
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # DisplayName
    output.write(b'\x4D')  # DisplayName tag (0x0D + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'Inbox') # DisplayName
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Type
    output.write(b'\x4E')  # Type tag (0x0E + content flag)
    output.write(b'\x03')  # STR_I
    output.write(b'2')     # Type (Inbox = 2)
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # End Add
    output.write(b'\x01')  # END tag
    
    # End Changes
    output.write(b'\x01')  # END tag
    
    # End FolderSync
    output.write(b'\x01')  # END tag
    
    return output.getvalue()

def test_zpush_wbxml():
    """Test the Z-Push-style WBXML response"""
    wbxml = create_zpush_style_foldersync_wbxml('1')
    print(f"Z-Push-style WBXML length: {len(wbxml)}")
    print(f"Z-Push-style WBXML hex: {wbxml.hex()}")
    return wbxml

if __name__ == "__main__":
    test_zpush_wbxml()
