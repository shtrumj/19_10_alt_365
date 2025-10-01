"""
Simple WBXML Response Generator for ActiveSync
Creates basic WBXML responses for common ActiveSync commands
"""

def create_foldersync_wbxml_response(sync_key: str = "1", count: int = 7) -> bytes:
    """
    Create a simple WBXML response for FolderSync command
    
    This is a minimal implementation that creates a basic WBXML structure
    for the FolderSync response that iPhone clients can understand.
    """
    
    # WBXML version 1.3, Public ID for ActiveSync, UTF-8 charset
    wbxml_header = bytes([
        0x03, 0x01,  # WBXML version 1.3
        0x01, 0x6A, 0x00,  # Public ID for ActiveSync
        0x6A, 0x00,  # UTF-8 charset
        0x00, 0x00   # String table length (will be updated)
    ])
    
    # String table with common strings
    string_table = [
        "FolderSync",
        "Status", 
        "SyncKey",
        "Changes",
        "Count",
        "Add",
        "ServerId",
        "ParentId", 
        "DisplayName",
        "Type",
        "SupportedClasses",
        "SupportedClass",
        "Email",
        "Calendar",
        "Contacts",
        "Inbox",
        "Drafts", 
        "Deleted Items",
        "Sent Items",
        "Outbox",
        "Calendar",
        "Contacts"
    ]
    
    # Update string table length in header
    string_table_length = len(string_table)
    wbxml_header = wbxml_header[:-2] + bytes([string_table_length >> 8, string_table_length & 0xFF])
    
    # Create the WBXML body
    wbxml_body = bytearray()
    
    # FolderSync element start
    wbxml_body.append(0x05)  # FolderSync tag
    
    # Status element
    wbxml_body.append(0x06)  # Status tag
    wbxml_body.append(0x01)  # Value 1 (success)
    wbxml_body.append(0x01)  # END
    
    # SyncKey element  
    wbxml_body.append(0x07)  # SyncKey tag
    wbxml_body.append(0x80 | 0x02)  # String reference to "1"
    wbxml_body.append(0x01)  # END
    
    # Changes element
    wbxml_body.append(0x08)  # Changes tag
    
    # Count element
    wbxml_body.append(0x09)  # Count tag
    wbxml_body.append(0x80 | 0x04)  # String reference to count value
    wbxml_body.append(0x01)  # END
    
    # Add elements for each folder
    folders = [
        ("1", "0", "Inbox", "2", "Email"),
        ("2", "0", "Drafts", "3", "Email"), 
        ("3", "0", "Deleted Items", "4", "Email"),
        ("4", "0", "Sent Items", "5", "Email"),
        ("5", "0", "Outbox", "6", "Email"),
        ("calendar", "0", "Calendar", "8", "Calendar"),
        ("contacts", "0", "Contacts", "9", "Contacts")
    ]
    
    for server_id, parent_id, display_name, folder_type, supported_class in folders:
        # Add element start
        wbxml_body.append(0x0A)  # Add tag
        
        # ServerId
        wbxml_body.append(0x0B)  # ServerId tag
        wbxml_body.append(0x80 | 0x06)  # String reference
        wbxml_body.append(0x01)  # END
        
        # ParentId
        wbxml_body.append(0x0C)  # ParentId tag  
        wbxml_body.append(0x80 | 0x07)  # String reference
        wbxml_body.append(0x01)  # END
        
        # DisplayName
        wbxml_body.append(0x0D)  # DisplayName tag
        wbxml_body.append(0x80 | 0x08)  # String reference
        wbxml_body.append(0x01)  # END
        
        # Type
        wbxml_body.append(0x0E)  # Type tag
        wbxml_body.append(0x80 | 0x09)  # String reference
        wbxml_body.append(0x01)  # END
        
        # SupportedClasses
        wbxml_body.append(0x0F)  # SupportedClasses tag
        wbxml_body.append(0x10)  # SupportedClass tag
        wbxml_body.append(0x80 | 0x0C)  # String reference
        wbxml_body.append(0x01)  # END
        wbxml_body.append(0x01)  # END SupportedClasses
        
        wbxml_body.append(0x01)  # END Add
    
    wbxml_body.append(0x01)  # END Changes
    wbxml_body.append(0x01)  # END FolderSync
    
    # Convert string table to bytes
    string_table_bytes = bytearray()
    for string in string_table:
        string_bytes = string.encode('utf-8')
        string_table_bytes.append(len(string_bytes))
        string_table_bytes.extend(string_bytes)
    
    # Combine header, body, and string table
    result = wbxml_header + wbxml_body + string_table_bytes
    
    return bytes(result)


def create_sync_wbxml_response(sync_key: str = "1", emails: list = None) -> bytes:
    """
    Create a simple WBXML response for Sync command
    """
    if emails is None:
        emails = []
    
    # WBXML header
    wbxml_header = bytes([
        0x03, 0x01,  # WBXML version 1.3
        0x01, 0x6A, 0x00,  # Public ID for ActiveSync
        0x6A, 0x00,  # UTF-8 charset
        0x00, 0x00   # String table length
    ])
    
    # String table
    string_table = [
        "Sync",
        "Collections", 
        "Collection",
        "CollectionId",
        "Status",
        "SyncKey",
        "Commands"
    ]
    
    # Update string table length
    string_table_length = len(string_table)
    wbxml_header = wbxml_header[:-2] + bytes([string_table_length >> 8, string_table_length & 0xFF])
    
    # Create WBXML body
    wbxml_body = bytearray()
    
    # Sync element
    wbxml_body.append(0x05)  # Sync tag
    
    # Collections element
    wbxml_body.append(0x06)  # Collections tag
    
    # Collection element
    wbxml_body.append(0x07)  # Collection tag
    
    # CollectionId
    wbxml_body.append(0x08)  # CollectionId tag
    wbxml_body.append(0x80 | 0x03)  # String reference to "1"
    wbxml_body.append(0x01)  # END
    
    # Status
    wbxml_body.append(0x09)  # Status tag
    wbxml_body.append(0x01)  # Value 1 (success)
    wbxml_body.append(0x01)  # END
    
    # SyncKey
    wbxml_body.append(0x0A)  # SyncKey tag
    wbxml_body.append(0x80 | 0x05)  # String reference
    wbxml_body.append(0x01)  # END
    
    # Commands (empty for now)
    wbxml_body.append(0x0B)  # Commands tag
    wbxml_body.append(0x01)  # END
    
    wbxml_body.append(0x01)  # END Collection
    wbxml_body.append(0x01)  # END Collections
    wbxml_body.append(0x01)  # END Sync
    
    # Convert string table to bytes
    string_table_bytes = bytearray()
    for string in string_table:
        string_bytes = string.encode('utf-8')
        string_table_bytes.append(len(string_bytes))
        string_table_bytes.extend(string_bytes)
    
    # Combine all parts
    result = wbxml_header + wbxml_body + string_table_bytes
    
    return bytes(result)


def test_wbxml_responses():
    """Test the WBXML response generators"""
    print("Testing WBXML response generation...")
    
    # Test FolderSync
    foldersync_wbxml = create_foldersync_wbxml_response()
    print(f"FolderSync WBXML length: {len(foldersync_wbxml)}")
    print(f"FolderSync WBXML (first 20 bytes): {foldersync_wbxml[:20].hex()}")
    
    # Test Sync
    sync_wbxml = create_sync_wbxml_response()
    print(f"Sync WBXML length: {len(sync_wbxml)}")
    print(f"Sync WBXML (first 20 bytes): {sync_wbxml[:20].hex()}")
    
    print("WBXML response generation test completed!")


if __name__ == "__main__":
    test_wbxml_responses()
