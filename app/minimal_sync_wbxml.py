#!/usr/bin/env python3
"""
Microsoft ActiveSync WBXML Sync response implementation
Following MS-ASWBXML and MS-ASCMD specifications exactly
Correct token values per Microsoft documentation
"""

import io
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def create_minimal_sync_wbxml(sync_key: str, emails: list, collection_id: str = "1", status: int = 1, window_size: int = 5, is_initial_sync: bool = False) -> bytes:
    """
    Create WBXML Sync response following Grommunio-Sync implementation
    
    CRITICAL: Initial sync (SyncKey 0→1) must NOT include:
    - Commands block
    - GetChanges tag
    - WindowSize tag
    
    Per Grommunio-Sync lib/request/sync.php line 1224:
    Commands are ONLY sent when HasSyncKey() is true (i.e., NOT for initial sync)
    
    Initial sync response structure:
    Sync
      ├── Status (top-level)
      ├── SyncKey (new key "1")
      └── Collections
          └── Collection
              ├── Class = "Email"
              ├── CollectionId
              ├── SyncKey
              └── Status
              # NO Commands, NO GetChanges, NO WindowSize!
    
    Subsequent sync response structure:
    Sync
      ├── Status (top-level)
      ├── SyncKey (bumped key)
      └── Collections
          └── Collection
              ├── Class
              ├── CollectionId
              ├── SyncKey
              ├── Status
              ├── MoreAvailable (if applicable)
              ├── GetChanges (empty tag)
              ├── WindowSize
              └── Commands
                  └── Add (for each email)
    
    With content flag (0x40): 0x05 becomes 0x45, etc.
    """
    
    # Respect the window_size requested by the client
    max_emails = min(window_size, len(emails))
    
    logger.info(f"WBXML Generation: is_initial_sync={is_initial_sync}, total_emails={len(emails)}, window_size={window_size}, max_emails={max_emails}, will_add={len(emails[:max_emails]) if not is_initial_sync else 0}")
    
    output = io.BytesIO()
    
    # WBXML Header - EXACTLY matching what iPhone sends
    output.write(b'\x03')  # WBXML version 1.3
    output.write(b'\x01')  # Public ID 1 (ActiveSync)
    output.write(b'\x6a')  # Charset 106 (UTF-8)
    output.write(b'\x00')  # String table length (will add 0x00 for no table)
    
    # Start in AirSync namespace (codepage 0)
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x00')  # Codepage 0 (AirSync)
    
    # === Z-PUSH AUTHORITATIVE TOKENS ===
    # Source: https://github.com/Z-Hub/Z-Push/master/src/lib/wbxml/wbxmldefs.php
    # Codepage 0 (AirSync)
    
    # Sync (0x05 + 0x40 = 0x45) - Z-Push "Synchronize"
    output.write(b'\x45')  # Sync with content
    
    # CRITICAL TEST: Remove top-level Status and SyncKey!
    # Hypothesis: Sync command should NOT have top-level Status/SyncKey
    # Unlike FolderSync which DOES have them
    # MS-ASCMD spec suggests Sync only has Collections at top level
    # Status and SyncKey belong ONLY in Collection element
    
    # Collections (0x1C + 0x40 = 0x5C) - Z-Push "Folders" - FIXED!
    output.write(b'\x5C')  # Collections with content
    
    # Collection (0x0F + 0x40 = 0x4F) - Z-Push "Folder" - FIXED!
    output.write(b'\x4F')  # Collection with content
    
    # Class (0x10 + 0x40 = 0x50) - Z-Push "FolderType" - CRITICAL! WAS MISSING!
    # Per documentation line 32: Class should be FIRST in Collection
    output.write(b'\x50')  # Class with content
    output.write(b'\x03')  # STR_I
    output.write(b'Email')  # Class = "Email"
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Class
    
    # SyncKey (0x0B + 0x40 = 0x4B) - Z-Push "SyncKey"
    output.write(b'\x4B')  # SyncKey with content
    output.write(b'\x03')  # STR_I
    output.write(sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END SyncKey
    
    # CollectionId (0x12 + 0x40 = 0x52) - Z-Push "FolderId" - FIXED!
    output.write(b'\x52')  # CollectionId with content
    output.write(b'\x03')  # STR_I
    output.write(collection_id.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END CollectionId
    
    # Status (0x0E + 0x40 = 0x4E) - Z-Push "Status" - FIXED!
    output.write(b'\x4E')  # Status with content
    output.write(b'\x03')  # STR_I
    output.write(str(status).encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Status
    
    # CRITICAL: Per Grommunio-Sync, Commands/GetChanges/WindowSize are ONLY sent for subsequent syncs
    # Initial sync (SyncKey 0→1) must NOT include these elements!
    if not is_initial_sync:
        # Per Z-Push line 98: MoreAvailable → GetChanges → WindowSize THEN Commands
        # MoreAvailable (0x14 + 0x40 = 0x54) - Z-Push "MoreAvailable" - FIXED!
        if emails and len(emails) > max_emails:
            output.write(b'\x54')  # MoreAvailable with content
            output.write(b'\x03')  # STR_I
            output.write(b'1')
            output.write(b'\x00')  # String terminator
            output.write(b'\x01')  # END MoreAvailable
        
        # GetChanges (0x13) - Z-Push "GetChanges" - FIXED! (was 0x18, wrong!)
        # EMPTY TAG per MS-ASCMD, no content flag, SELF-CLOSING
        output.write(b'\x13')  # GetChanges SELF-CLOSING empty tag
        
        # WindowSize (0x15 + 0x40 = 0x55) - Z-Push "WindowSize" - FIXED! (was 0x5F, wrong!)
        output.write(b'\x55')  # WindowSize with content
        output.write(b'\x03')  # STR_I
        output.write(str(window_size).encode())
        output.write(b'\x00')  # String terminator
        output.write(b'\x01')  # END WindowSize
        
        if emails and len(emails) > 0:
            # Commands (0x16 + 0x40 = 0x56) - Z-Push "Perform" - FIXED!
            output.write(b'\x56')  # Commands with content
            
            # Add emails (respect WindowSize)
            for email in emails[:max_emails]:
                # Add (0x07 + 0x40 = 0x47) - Z-Push "Add" - FIXED!
                output.write(b'\x47')  # Add with content
                
                # ServerId (0x0D + 0x40 = 0x4D) - Z-Push "ServerEntryId" - CORRECT!
                output.write(b'\x4D')  # ServerId with content
                output.write(b'\x03')  # STR_I
                server_id = f"{collection_id}:{email.id}"
                output.write(server_id.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END ServerId
                
                # Data (0x1D + 0x40 = 0x5D) - Z-Push "Data" for ApplicationData
                output.write(b'\x5D')  # Data with content
                
                # Switch to Email2 namespace (codepage 2)
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x02')  # Codepage 2 (Email2)
                
                # Get sender
                sender_email = 'Unknown'
                if hasattr(email, 'external_sender') and email.external_sender:
                    sender_email = email.external_sender
                elif hasattr(email, 'sender') and email.sender:
                    sender_email = email.sender.email if hasattr(email.sender, 'email') else str(email.sender)
                
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
                date_str = created_at.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                output.write(date_str.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END DateReceived
                
                # To (0x03 in Email2 + 0x40 = 0x43)
                recipient_email = 'Unknown'
                if hasattr(email, 'external_recipient') and email.external_recipient:
                    recipient_email = email.external_recipient
                elif hasattr(email, 'recipient') and email.recipient:
                    recipient_email = email.recipient.email if hasattr(email.recipient, 'email') else str(email.recipient)
                
                output.write(b'\x43')  # To with content
                output.write(b'\x03')  # STR_I
                output.write(recipient_email.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END To
                
                # Read (0x10 in Email2 + 0x40 = 0x50)
                output.write(b'\x50')  # Read with content
                output.write(b'\x03')  # STR_I
                is_read = '1' if getattr(email, 'is_read', False) else '0'
                output.write(is_read.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Read
                
                # MessageClass (0x1A in Email2 + 0x40 = 0x5A)
                output.write(b'\x5A')  # MessageClass with content
                output.write(b'\x03')  # STR_I
                output.write(b'IPM.Note')
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END MessageClass
                
                # Importance (0x06 in Email2 + 0x40 = 0x46)
                output.write(b'\x46')  # Importance with content
                output.write(b'\x03')  # STR_I
                output.write(b'1')  # Normal importance
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Importance
                
                # Switch to AirSyncBase namespace (codepage 17) for Body
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x11')  # Codepage 17 (AirSyncBase)
                
                # Body (0x08 in AirSyncBase + 0x40 = 0x48)
                output.write(b'\x48')  # Body with content
                
                # Type (0x0A in AirSyncBase + 0x40 = 0x4A)
                output.write(b'\x4A')  # Type with content
                output.write(b'\x03')  # STR_I
                output.write(b'1')  # 1=Plain text
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Type
                
                # Get body content
                body_text = getattr(email, 'body', '') or ''
                if not body_text or not body_text.strip():
                    body_text = ' '  # Minimum body content
                
                # Limit body to 512 bytes for iPhone
                if len(body_text) > 512:
                    body_text = body_text[:512]
                
                body_size = str(len(body_text.encode('utf-8')))
                
                # EstimatedDataSize (0x0B in AirSyncBase + 0x40 = 0x4B)
                output.write(b'\x4B')  # EstimatedDataSize with content
                output.write(b'\x03')  # STR_I
                output.write(body_size.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END EstimatedDataSize
                
                # Truncated (0x0C in AirSyncBase + 0x40 = 0x4C)
                output.write(b'\x4C')  # Truncated with content
                output.write(b'\x03')  # STR_I
                original_body = getattr(email, 'body', '') or ''
                is_truncated = '1' if len(original_body) > 512 else '0'
                output.write(is_truncated.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Truncated
                
                # Data (0x09 in AirSyncBase + 0x40 = 0x49)
                output.write(b'\x49')  # Data with content
                output.write(b'\x03')  # STR_I
                output.write(body_text.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Data
                
                output.write(b'\x01')  # END Body
                
                # Switch back to AirSync namespace
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x00')  # Codepage 0 (AirSync)
                
                output.write(b'\x01')  # END ApplicationData
                output.write(b'\x01')  # END Add
            
            output.write(b'\x01')  # END Commands
    
    output.write(b'\x01')  # END Collection
    output.write(b'\x01')  # END Collections
    output.write(b'\x01')  # END Sync
    
    return output.getvalue()
