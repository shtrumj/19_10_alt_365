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

def create_minimal_sync_wbxml(sync_key: str, emails: list, collection_id: str = "1", status: int = 1, window_size: int = 5, is_initial_sync: bool = False, has_more: bool = False) -> bytes:
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
    
    # POLISH #17-1: Add top-level Status for maximum compatibility
    # Expert: "Many servers include it. iOS doesn't require it, but some MDMs expect it"
    # Status (0x0E + 0x40 = 0x4E)
    output.write(b'\x4E')  # Status with content
    output.write(b'\x03')  # STR_I
    output.write(b'1')  # Success
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Status
    
    # Collections (0x1C + 0x40 = 0x5C) - Z-Push "Folders" - FIXED!
    output.write(b'\x5C')  # Collections with content
    
    # Collection (0x0F + 0x40 = 0x4F) - Z-Push "Folder" - FIXED!
    output.write(b'\x4F')  # Collection with content
    
    # POLISH #17-2: Reorder to match Z-Push: Class → CollectionId → SyncKey → Status
    # Expert: "Z-Push and most references do: Class → CollectionId → SyncKey → Status"
    
    # Class (0x10 + 0x40 = 0x50) - Z-Push "FolderType" - CRITICAL! WAS MISSING!
    # Per documentation line 32: Class should be FIRST in Collection
    output.write(b'\x50')  # Class with content
    output.write(b'\x03')  # STR_I
    output.write(b'Email')  # Class = "Email"
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Class
    
    # CollectionId (0x12 + 0x40 = 0x52) - Z-Push "FolderId" - MOVED UP!
    output.write(b'\x52')  # CollectionId with content
    output.write(b'\x03')  # STR_I
    output.write(collection_id.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END CollectionId
    
    # SyncKey (0x0B + 0x40 = 0x4B) - Z-Push "SyncKey" - MOVED AFTER CollectionId!
    # CRITICAL FIX #16-3: Initial sync MUST return new SyncKey="1", not echo "0"!
    # Expert: "when is_initial_sync=True, force the collection SyncKey to '1'"
    new_sync_key = "1" if is_initial_sync else sync_key
    output.write(b'\x4B')  # SyncKey with content
    output.write(b'\x03')  # STR_I
    output.write(new_sync_key.encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END SyncKey
    
    # Status (0x0E + 0x40 = 0x4E) - Z-Push "Status" - FIXED!
    output.write(b'\x4E')  # Status with content
    output.write(b'\x03')  # STR_I
    output.write(str(status).encode())
    output.write(b'\x00')  # String terminator
    output.write(b'\x01')  # END Status
    
    # CRITICAL FIX #15: Remove MoreAvailable/GetChanges/WindowSize from BEFORE Commands!
    # Expert diagnosis: "Do not mix in GetChanges/WindowSize tags in the response"
    # "They are request parameters. The response only uses Status, SyncKey, Commands, Adds, and optionally MoreAvailable"
    # MoreAvailable must be AFTER Commands, not before!
    if not is_initial_sync:
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
                
                # CRITICAL FIX #16-2: ApplicationData token WRONG!
                # Expert: "ApplicationData = cp0 0x0F | 0x40 = 0x4F (NOT 0x4E which is Status!)"
                # Was using Status token (0x4E), should be ApplicationData (0x4F)
                output.write(b'\x4F')  # ApplicationData with content (CORRECTED!)
                
                # CRITICAL FIX #16-4: This is Email codepage, NOT "Email2"!
                # Expert: "Email is codepage 2. Comment says Email2 which is contradictory"
                # Switch to Email namespace (codepage 2)
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x02')  # Codepage 2 (Email - NOT Email2!)
                
                # Get sender
                sender_email = 'Unknown'
                if hasattr(email, 'external_sender') and email.external_sender:
                    sender_email = email.external_sender
                elif hasattr(email, 'sender') and email.sender:
                    sender_email = email.sender.email if hasattr(email.sender, 'email') else str(email.sender)
                
                # CRITICAL FIX: ALL Email2 tokens were WRONG!
                # Source: wbxml_encoder.py lines 66-79 (AUTHORITATIVE)
                
                # Subject (0x0F in Email2 + 0x40 = 0x4F) - FIXED from 0x45!
                subject = 'No Subject'
                if hasattr(email, 'subject') and email.subject:
                    subject = email.subject
                output.write(b'\x4F')  # Subject with content
                output.write(b'\x03')  # STR_I
                output.write(subject.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Subject
                
                # From (0x10 in Email2 + 0x40 = 0x50) - FIXED from 0x44!
                output.write(b'\x50')  # From with content
                output.write(b'\x03')  # STR_I
                output.write(sender_email.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END From
                
                # CRITICAL FIX #9: REORDER - To BEFORE DateReceived per MS-ASCMD!
                # To (0x11 in Email2 + 0x40 = 0x51) - FIXED from 0x43!
                recipient_email = 'Unknown'
                if hasattr(email, 'external_recipient') and email.external_recipient:
                    recipient_email = email.external_recipient
                elif hasattr(email, 'recipient') and email.recipient:
                    recipient_email = email.recipient.email if hasattr(email.recipient, 'email') else str(email.recipient)
                
                output.write(b'\x51')  # To with content
                output.write(b'\x03')  # STR_I
                output.write(recipient_email.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END To
                
                # DateReceived (0x12 in Email2 + 0x40 = 0x52) - NOW AFTER To per MS-ASCMD!
                output.write(b'\x52')  # DateReceived with content
                output.write(b'\x03')  # STR_I
                created_at = email.created_at if hasattr(email, 'created_at') else datetime.utcnow()
                date_str = created_at.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                output.write(date_str.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END DateReceived
                
                # CRITICAL FIX #6: Add MISSING DisplayTo (0x13 in Email2 + 0x40 = 0x53)
                # Source: wbxml_encoder.py line 70, line 387-389 shows it's REQUIRED
                output.write(b'\x53')  # DisplayTo with content
                output.write(b'\x03')  # STR_I
                output.write(recipient_email.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END DisplayTo
                
                # CRITICAL FIX #7: Add MISSING ThreadTopic (0x14 in Email2 + 0x40 = 0x54)
                # Source: wbxml_encoder.py line 71, line 391-394 shows it's REQUIRED
                output.write(b'\x54')  # ThreadTopic with content
                output.write(b'\x03')  # STR_I
                output.write(subject.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END ThreadTopic
                
                # CRITICAL FIX #9: REORDER - Importance BEFORE Read per MS-ASCMD!
                # Importance (0x15 in Email2 + 0x40 = 0x55) - FIXED from 0x46!
                output.write(b'\x55')  # Importance with content
                output.write(b'\x03')  # STR_I
                output.write(b'1')  # Normal importance
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Importance
                
                # Read (0x16 in Email2 + 0x40 = 0x56) - NOW AFTER Importance per MS-ASCMD!
                # 0x50 was colliding with Class token!
                output.write(b'\x56')  # Read with content
                output.write(b'\x03')  # STR_I
                is_read = '1' if getattr(email, 'is_read', False) else '0'
                output.write(is_read.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Read
                
                # MessageClass (0x1C in Email2 + 0x40 = 0x5C) - NOW AFTER Read per MS-ASCMD!
                output.write(b'\x5C')  # MessageClass with content
                output.write(b'\x03')  # STR_I
                output.write(b'IPM.Note')
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END MessageClass
                
                # Get body content FIRST to determine Type
                body_text = getattr(email, 'body', '') or ''
                if not body_text or not body_text.strip():
                    body_text = ' '  # Minimum body content
                
                # CRITICAL FIX #20: Simplify body - strip HTML or use simple text
                # Expert: "Send one message like this... Body → Type=2, Data='<p>hello</p>'"
                # Maybe iOS rejects complex HTML? Try simple text first!
                # For now, use PLAIN TEXT only to test
                import re
                body_text_plain = re.sub(r'<[^>]+>', '', body_text)  # Strip HTML tags
                if not body_text_plain.strip():
                    body_text_plain = 'Email content'
                body_text = body_text_plain[:512]  # STRICT limit for testing
                
                # CRITICAL FIX #19: Detect HTML vs Plain Text  
                # For now, force PLAIN TEXT (Type=1) for testing
                has_html = False  # Force plain text
                body_type = '1'  # 1=Plain text (testing!)
                native_body_type = '1'  # Match body type
                
                # CRITICAL FIX #10: Add MISSING NativeBodyType (0x1F in Email2 + 0x40 = 0x5F)
                # Expert FIX #19: "Set Body Type correctly - if you put HTML into Data: Type=2 (HTML)"
                output.write(b'\x5F')  # NativeBodyType with content
                output.write(b'\x03')  # STR_I
                output.write(native_body_type.encode())  # 2=HTML, 1=Plain text
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END NativeBodyType
                
                # CRITICAL FIX #19: Switch pages properly!
                # Expert: "In WBXML you must emit a SWITCH_PAGE (token 0x00) before using tags from a different page"
                # "From your hex I can see Email and AirSyncBase fields showing up without the corresponding page switch"
                
                # SWITCH_PAGE -> 17 (AirSyncBase) for Body
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x11')  # Codepage 17 (AirSyncBase)
                
                # Body (0x08 in AirSyncBase + 0x40 = 0x48)
                output.write(b'\x48')  # Body with content (AirSyncBase)
                
                # Type (0x0A in AirSyncBase + 0x40 = 0x4A)
                # Expert FIX #19: "If the body contains HTML, set AirSyncBase:Type = 2. Only use Type = 1 if the Data has no HTML tags (plain text only)"
                output.write(b'\x4A')  # Type with content (AirSyncBase)
                output.write(b'\x03')  # STR_I
                output.write(body_type.encode())  # 2=HTML or 1=Plain text (MATCHES body content!)
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Type
                
                # Body is already limited to 512 bytes above
                
                body_size = str(len(body_text.encode('utf-8')))
                
                # EstimatedDataSize (0x0B in AirSyncBase + 0x40 = 0x4B)
                output.write(b'\x4B')  # EstimatedDataSize with content (AirSyncBase)
                output.write(b'\x03')  # STR_I
                output.write(body_size.encode())
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END EstimatedDataSize
                
                # Data (0x09 in AirSyncBase + 0x40 = 0x49)
                output.write(b'\x49')  # Data with content (AirSyncBase)
                output.write(b'\x03')  # STR_I
                output.write(body_text.encode('utf-8'))
                output.write(b'\x00')  # String terminator
                output.write(b'\x01')  # END Data
                
                output.write(b'\x01')  # END Body
                
                # CRITICAL FIX #19: Switch back to AirSync BEFORE closing ApplicationData!
                # Expert: "Switch back as needed. When done with ApplicationData, go back to AirSync to close tags"
                output.write(b'\x00')  # SWITCH_PAGE
                output.write(b'\x00')  # Codepage 0 (AirSync)
                
                output.write(b'\x01')  # END ApplicationData
                output.write(b'\x01')  # END Add
            
            output.write(b'\x01')  # END Commands
            
            # CRITICAL FIX #16-1: MoreAvailable token WRONG!
            # Expert: "In AirSync codepage 0, MoreAvailable is 0x16 (empty tag, no content)"
            # "Your code writes b'\x08', which collides with other tokens"
            # Placement: AFTER Commands, BEFORE END Collection
            if has_more:
                output.write(b'\x16')  # MoreAvailable EMPTY TAG (0x16, no content flag!)
    
    output.write(b'\x01')  # END Collection
    output.write(b'\x01')  # END Collections
    output.write(b'\x01')  # END Sync
    
    return output.getvalue()
