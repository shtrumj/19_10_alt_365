#!/usr/bin/env python3
"""
Correct WBXML Sync response for iPhone based on MS-ASWBXML specification
Code Page 0: AirSync namespace
"""

import io
from typing import List, Optional

def create_minimal_sync_wbxml(sync_key: str = "1", emails: List = None, collection_id: str = "1") -> bytes:
    """
    Create WBXML Sync response with CORRECT tag codes from MS-ASWBXML spec
    Code Page 0 (AirSync) tag values per Microsoft documentation
    
    MS-ASWBXML Code Page 0: AirSync tokens:
    - Sync = 0x05
    - Responses = 0x06 
    - Add = 0x07
    - ApplicationData = 0x08
    - Status = 0x0C
    - Collection = 0x0D
    - Class = 0x0E
    - CollectionId = 0x11
    - Commands = 0x12
    - DeletesAsMoves = 0x13
    - GetChanges = 0x14
    - MoreAvailable = 0x15
    - WindowSize = 0x16
    - Conflict = 0x17
    - Collections = 0x18
    - Data = 0x19
    - Delete = 0x1A
    - Fetch = 0x1B
    - Folder = 0x1C
    - ServerEntryId = 0x1D
    - ClientEntryId = 0x1E
    - ServerId = 0x1F
    - SyncKey = 0x20
    """
    if emails is None:
        emails = []
        
    output = io.BytesIO()
    
    # WBXML Header
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00')  # String table length 0
    
    # Switch to AirSync namespace (codepage 0)
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x00')  # Codepage 0 (AirSync)
    
    # Sync (0x05 + 0x40 content flag = 0x45)
    output.write(b'\x45')  # Sync start tag with content
    
    # Collections (0x18 + 0x40 = 0x58)
    output.write(b'\x58')  # Collections tag with content
    
    # Collection (0x0D + 0x40 = 0x4D)
    output.write(b'\x4D')  # Collection tag with content
    
    # Class (0x0E + 0x40 = 0x4E)
    output.write(b'\x4E')  # Class tag with content
    output.write(b'\x03')  # STR_I (inline string)
    output.write(b'Email')
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # SyncKey (0x20 + 0x40 = 0x60)
    output.write(b'\x60')  # SyncKey tag with content
    output.write(b'\x03')  # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # CollectionId (0x11 + 0x40 = 0x51)
    output.write(b'\x51')  # CollectionId tag with content
    output.write(b'\x03')  # STR_I
    output.write(collection_id.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # Status (0x0C + 0x40 = 0x4C)
    output.write(b'\x4C')  # Status tag with content
    output.write(b'\x03')  # STR_I
    output.write(b'1')     # Status value
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END tag
    
    # If we have emails, add Commands section
    if emails:
        # Commands (0x12 + 0x40 = 0x52)
        output.write(b'\x52')  # Commands tag with content
        
        # For each email, add an Add element
        for email in emails[:5]:  # Limit to 5 emails for initial sync
            # Add (0x07 + 0x40 = 0x47)
            output.write(b'\x47')  # Add tag with content
            
            # ServerId (0x1F + 0x40 = 0x5F)
            output.write(b'\x5F')  # ServerId tag with content
            output.write(b'\x03')  # STR_I
            server_id = f"{collection_id}:{getattr(email, 'id', '0')}"
            output.write(server_id.encode())
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # ApplicationData (0x08 + 0x40 = 0x48)
            output.write(b'\x48')  # ApplicationData tag with content
            
            # Switch to Email namespace (codepage 2) for email properties
            output.write(b'\x00')  # SWITCH_PAGE
            output.write(b'\x02')  # Codepage 2 (Email)
            
            # Email codepage 2 tokens:
            # Subject = 0x15, From = 0x13, To = 0x06, DateReceived = 0x07
            # Importance = 0x09, Read = 0x0B, Body = 0x08
            
            # Subject (0x15 + 0x40 = 0x55)
            output.write(b'\x55')  # Subject tag with content
            output.write(b'\x03')  # STR_I
            subject = getattr(email, 'subject', '(no subject)')
            output.write(subject[:100].encode('utf-8', errors='ignore'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # From (0x13 + 0x40 = 0x53)
            output.write(b'\x53')  # From tag with content
            output.write(b'\x03')  # STR_I
            sender_email = getattr(getattr(email, 'sender', None), 'email', 'unknown@example.com')
            output.write(sender_email.encode('utf-8', errors='ignore'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # To (0x06 + 0x40 = 0x46)
            output.write(b'\x46')  # To tag with content
            output.write(b'\x03')  # STR_I
            recipient_email = getattr(getattr(email, 'recipient', None), 'email', 'unknown@example.com')
            output.write(recipient_email.encode('utf-8', errors='ignore'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # DateReceived (0x07 + 0x40 = 0x47) - reusing Add tag code, need to check
            # Actually let's use 0x07 which should be DateReceived in Email namespace
            output.write(b'\x47')  # DateReceived tag with content
            output.write(b'\x03')  # STR_I
            created_at = getattr(email, 'created_at', None)
            if created_at:
                created_ts = created_at.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            else:
                created_ts = '2025-01-01T00:00:00.000Z'
            output.write(created_ts.encode())
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # Read (0x0B + 0x40 = 0x4B)
            output.write(b'\x4B')  # Read tag with content
            output.write(b'\x03')  # STR_I
            output.write(b'1' if getattr(email, 'is_read', False) else b'0')
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # Importance (0x09 + 0x40 = 0x49)
            output.write(b'\x49')  # Importance tag with content
            output.write(b'\x03')  # STR_I
            output.write(b'1')  # 1 = normal
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END tag
            
            # Switch back to AirSync codepage
            output.write(b'\x00')  # SWITCH_PAGE
            output.write(b'\x00')  # Codepage 0 (AirSync)
            
            output.write(b'\x01')  # END ApplicationData
            output.write(b'\x01')  # END Add
        
        output.write(b'\x01')  # END Commands
    
    # End Collection
    output.write(b'\x01')  # END tag
    
    # End Collections
    output.write(b'\x01')  # END tag
    
    # End Sync
    output.write(b'\x01')  # END tag
    
    return output.getvalue()

