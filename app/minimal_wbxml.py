# File: app/minimal_wbxml.py

#!/usr/bin/env python3
"""
Minimal WBXML FolderSync response for iPhone compatibility
Uses correct FolderHierarchy namespace codes
"""

import io

def create_minimal_foldersync_wbxml(sync_key: str = "1") -> bytes:
    """
    Create a minimal WBXML FolderSync response with correct tag codes
    FolderHierarchy namespace is codepage 1
    """
    output = io.BytesIO()
    
    # WBXML Header
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00')  # String table length 0 (1 byte)
    
    # Switch to FolderHierarchy namespace (codepage 7)
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x07')  # Codepage 7 (FolderHierarchy)
    
    # FolderSync (0x05 with content flag = 0x45)
    output.write(b'\x45')  # FolderSync start tag with content
    
    # Status (0x06 with content flag = 0x46)
    output.write(b'\x46')  # Status tag with content
    output.write(b'\x03')  # STR_I (inline string)
    output.write(b'1')     # Status value
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # SyncKey (0x07 with content flag = 0x47)
    output.write(b'\x47')  # SyncKey tag with content
    output.write(b'\x03')  # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Changes (0x08 with content flag = 0x48)
    output.write(b'\x48')  # Changes tag with content
    
    # Count (0x09 with content flag = 0x49)
    output.write(b'\x49')  # Count tag with content
    output.write(b'\x03')  # STR_I
    output.write(b'5')     # Count = 5 folders
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Define folders to add
    folders = [
        ('1', '0', 'Inbox', '2'),
        ('2', '0', 'Drafts', '3'),
        ('3', '0', 'Deleted Items', '4'),
        ('4', '0', 'Sent Items', '5'),
        ('5', '0', 'Outbox', '6'),
    ]
    
    for server_id, parent_id, display_name, folder_type in folders:
        # Add (0x0A with content flag = 0x4A)
        output.write(b'\x4A')  # Add tag with content
        
        # ServerId (0x0B with content flag = 0x4B)
        output.write(b'\x4B')  # ServerId tag with content
        output.write(b'\x03')  # STR_I
        output.write(server_id.encode())
        output.write(b'\x00')  # String terminator
        output.write(b'\x01')  # END tag
        
        # ParentId (0x0C with content flag = 0x4C)
        output.write(b'\x4C')  # ParentId tag with content
        output.write(b'\x03')  # STR_I
        output.write(parent_id.encode())
        output.write(b'\x00')  # String terminator
        output.write(b'\x01')  # END tag
        
        # DisplayName (0x0D with content flag = 0x4D)
        output.write(b'\x4D')  # DisplayName tag with content
        output.write(b'\x03')  # STR_I
        output.write(display_name.encode())
        output.write(b'\x00')  # String terminator
        output.write(b'\x01')  # END tag
        
        # Type (0x0E with content flag = 0x4E)
        output.write(b'\x4E')  # Type tag with content
        output.write(b'\x03')  # STR_I
        output.write(folder_type.encode())
        output.write(b'\x00')  # String terminator
        output.write(b'\x01')  # END tag
        
        # End Add
        output.write(b'\x01')  # END tag
    
    # End Changes
    output.write(b'\x01')  # END tag
    
    # End FolderSync
    output.write(b'\x01')  # END tag
    
    return output.getvalue()

def test_minimal_wbxml():
    """Test the minimal WBXML response"""
    wbxml = create_minimal_foldersync_wbxml('1')
    print(f"Minimal WBXML length: {len(wbxml)}")
    print(f"Minimal WBXML hex (first 50 bytes): {wbxml[:50].hex()}")
    return wbxml

if __name__ == "__main__":
    test_minimal_wbxml()