#!/usr/bin/env python3
"""
Microsoft ActiveSync WBXML Sync response implementation
Following MS-ASWBXML specification exactly as per Microsoft documentation
"""

import io
from datetime import datetime

def create_minimal_sync_wbxml(sync_key: str, emails: list, collection_id: str = "1", status: int = 1) -> bytes:
    """
    Create minimal WBXML Sync response that iPhone will accept
    """
    output = io.BytesIO()
    
    # WBXML Header
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00')  # String table length 0
    
    # Start in AirSync namespace (codepage 0)
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x00')  # Codepage 0 (AirSync)
    
    # Sync (0x14 + 0x40 = 0x54)
    output.write(b'\x54')  # Sync with content
    
    # Collections (0x0F + 0x40 = 0x4F)
    output.write(b'\x4F')  # Collections with content
    
    # Collection (0x0E + 0x40 = 0x4E)
    output.write(b'\x4E')  # Collection with content
    
    # Class (0x10 + 0x40 = 0x50)
    output.write(b'\x50')  # Class with content
    output.write(b'\x03')  # STR_I
    output.write(b'Email')
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Class
    
    # SyncKey (0x0B + 0x40 = 0x4B)
    output.write(b'\x4B')  # SyncKey with content
    output.write(b'\x03')  # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END SyncKey
    
    # CollectionId (0x0C + 0x40 = 0x4C)
    output.write(b'\x4C')  # CollectionId with content
    output.write(b'\x03')  # STR_I
    output.write(collection_id.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END CollectionId
    
    # Status (0x0D + 0x40 = 0x4D)
    output.write(b'\x4D')  # Status with content
    output.write(b'\x03')  # STR_I
    output.write(str(status).encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Status
    
    if emails and len(emails) > 0:
        # Commands (0x13 + 0x40 = 0x53)
        output.write(b'\x53')  # Commands with content
        
        # Add only first 5 emails to avoid overwhelming
        for email in emails[:5]:
            # Add (0x07 + 0x40 = 0x47)
            output.write(b'\x47')  # Add with content
            
            # ServerId (0x08 + 0x40 = 0x48)
            output.write(b'\x48')  # ServerId with content
            output.write(b'\x03')  # STR_I
            server_id = f"{collection_id}:{email.id}"
            output.write(server_id.encode())
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END ServerId
            
            # ApplicationData (0x09 + 0x40 = 0x49)
            output.write(b'\x49')  # ApplicationData with content
            
            # Switch to Email2 namespace (codepage 2)
            output.write(b'\x00')  # SWITCH_PAGE
            output.write(b'\x02')  # Codepage 2 (Email2)
            
            # Get sender - for external emails, use external_sender field
            sender_email = 'shtrumj@gmail.com'  # Default
            if hasattr(email, 'external_sender') and email.external_sender is not None:
                sender_email = email.external_sender  # External email string
            elif hasattr(email, 'sender') and email.sender is not None:
                sender_email = email.sender.email  # Internal user email
            
            # From (0x04 in Email2 + 0x40 = 0x44)
            output.write(b'\x44')  # From with content
            output.write(b'\x03')  # STR_I
            output.write(sender_email.encode('utf-8'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END From
            
            # Subject (0x05 in Email2 + 0x40 = 0x45)
            subject = 'No Subject'
            if hasattr(email, 'subject') and email.subject:
                subject = email.subject
            output.write(b'\x45')  # Subject with content
            output.write(b'\x03')  # STR_I
            output.write(subject.encode('utf-8'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END Subject
            
            # DateReceived (0x0F in Email2 + 0x40 = 0x4F)
            output.write(b'\x4F')  # DateReceived with content
            output.write(b'\x03')  # STR_I
            created_at = email.created_at if hasattr(email, 'created_at') else datetime.utcnow()
            # Use ISO format that iPhone expects
            date_str = created_at.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            output.write(date_str.encode())
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END DateReceived
            
            # To (0x03 in Email2 + 0x40 = 0x43) 
            recipient_email = 'yonatan@shtrum.com'  # Default
            if hasattr(email, 'external_recipient') and email.external_recipient is not None:
                recipient_email = email.external_recipient  # External email string
            elif hasattr(email, 'recipient') and email.recipient is not None and hasattr(email.recipient, 'email'):
                recipient_email = email.recipient.email  # Internal user email
                    
            output.write(b'\x43')  # To with content
            output.write(b'\x03')  # STR_I
            output.write(recipient_email.encode('utf-8'))
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END To
            
            # Read flag (0x10 in Email2 + 0x40 = 0x50)
            output.write(b'\x50')  # Read with content
            output.write(b'\x03')  # STR_I
            is_read = '1' if getattr(email, 'is_read', False) else '0'
            output.write(is_read.encode())
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END Read
            
            # Switch back to AirSync
            output.write(b'\x00')  # SWITCH_PAGE
            output.write(b'\x00')  # Codepage 0 (AirSync)
            
            output.write(b'\x01')  # END ApplicationData
            output.write(b'\x01')  # END Add
        
        output.write(b'\x01')  # END Commands
    
    # MoreAvailable (0x12 + 0x40 = 0x52) - if there are more emails
    if emails and len(emails) > 5:
        output.write(b'\x52')  # MoreAvailable (empty tag)
    
    output.write(b'\x01')  # END Collection
    output.write(b'\x01')  # END Collections
    output.write(b'\x01')  # END Sync
    
    return output.getvalue()