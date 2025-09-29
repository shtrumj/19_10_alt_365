"""
MAPI Message Store Implementation

This module implements the MAPI message store functionality, including:
- Folder hierarchy (Inbox, Sent Items, Drafts, etc.)
- Message properties and content
- Property system integration
- Database mapping for emails and folders

This bridges our existing email database with MAPI protocol expectations.
"""

import struct
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime
import uuid

from .mapi_protocol import MapiProperty, MapiPropertyTags, MapiPropertyType
from .database import SessionLocal, Email, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class MapiFolderType(IntEnum):
    """MAPI folder types"""
    FOLDER_GENERIC = 1
    FOLDER_ROOT = 2
    FOLDER_SEARCH = 3

class MapiMessageFlags(IntEnum):
    """MAPI message flags"""
    MSGFLAG_READ = 0x00000001
    MSGFLAG_UNMODIFIED = 0x00000002
    MSGFLAG_SUBMIT = 0x00000004
    MSGFLAG_UNSENT = 0x00000008
    MSGFLAG_HASATTACH = 0x00000010
    MSGFLAG_FROMME = 0x00000020
    MSGFLAG_ASSOCIATED = 0x00000040
    MSGFLAG_RESEND = 0x00000080
    MSGFLAG_RN_PENDING = 0x00000100
    MSGFLAG_NRN_PENDING = 0x00000200

@dataclass
class MapiFolder:
    """MAPI folder representation"""
    folder_id: str
    parent_id: Optional[str]
    display_name: str
    folder_type: int
    content_count: int
    unread_count: int
    entry_id: bytes
    properties: Dict[int, Any]

@dataclass
class MapiMessage:
    """MAPI message representation"""
    message_id: str
    folder_id: str
    subject: str
    sender_name: str
    sender_email: str
    recipient_name: str
    recipient_email: str
    body_text: str
    body_html: str
    creation_time: datetime
    last_modification_time: datetime
    message_size: int
    message_flags: int
    entry_id: bytes
    properties: Dict[int, Any]

class MapiEntryIdGenerator:
    """Generate MAPI Entry IDs"""
    
    @staticmethod
    def generate_folder_entry_id(folder_id: str) -> bytes:
        """Generate folder entry ID"""
        # Simple implementation - in real Exchange this is more complex
        folder_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"folder:{folder_id}")
        return folder_uuid.bytes
    
    @staticmethod
    def generate_message_entry_id(message_id: str) -> bytes:
        """Generate message entry ID"""
        message_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"message:{message_id}")
        return message_uuid.bytes

class MapiPropertyConverter:
    """Convert between database fields and MAPI properties"""
    
    @staticmethod
    def email_to_mapi_properties(email: Email) -> Dict[int, Any]:
        """Convert Email object to MAPI properties"""
        properties = {}
        
        # Basic message properties
        if email.subject:
            properties[MapiPropertyTags.PR_SUBJECT] = email.subject
        if email.sender:
            properties[MapiPropertyTags.PR_SENDER_NAME] = email.sender
            properties[MapiPropertyTags.PR_SENDER_EMAIL_ADDRESS] = email.sender
        if email.recipient:
            properties[MapiPropertyTags.PR_RECEIVED_BY_NAME] = email.recipient
            properties[MapiPropertyTags.PR_RECEIVED_BY_EMAIL_ADDRESS] = email.recipient
        if email.body:
            properties[MapiPropertyTags.PR_BODY] = email.body
        if email.html_body:
            properties[MapiPropertyTags.PR_BODY_HTML] = email.html_body
        
        # Timestamps
        if email.created_at:
            properties[MapiPropertyTags.PR_CREATION_TIME] = email.created_at
            properties[MapiPropertyTags.PR_LAST_MODIFICATION_TIME] = email.created_at
        
        # Message class
        properties[MapiPropertyTags.PR_MESSAGE_CLASS] = "IPM.Note"
        
        # Message size (approximate)
        body_size = len(email.body or "") + len(email.html_body or "")
        properties[MapiPropertyTags.PR_MESSAGE_SIZE] = body_size
        
        # Message flags
        flags = 0
        if email.is_read:
            flags |= MapiMessageFlags.MSGFLAG_READ
        properties[MapiPropertyTags.PR_MESSAGE_FLAGS] = flags
        
        # Entry ID
        entry_id = MapiEntryIdGenerator.generate_message_entry_id(str(email.id))
        properties[MapiPropertyTags.PR_ENTRYID] = entry_id
        
        return properties
    
    @staticmethod
    def serialize_property_value(prop_type: int, value: Any) -> bytes:
        """Serialize MAPI property value to bytes"""
        try:
            if prop_type == MapiPropertyType.PT_UNICODE:
                if isinstance(value, str):
                    return value.encode('utf-16le') + b'\x00\x00'
                return b'\x00\x00'
            elif prop_type == MapiPropertyType.PT_STRING8:
                if isinstance(value, str):
                    return value.encode('utf-8') + b'\x00'
                return b'\x00'
            elif prop_type == MapiPropertyType.PT_LONG:
                return struct.pack('<I', int(value) if value else 0)
            elif prop_type == MapiPropertyType.PT_LONGLONG:
                return struct.pack('<Q', int(value) if value else 0)
            elif prop_type == MapiPropertyType.PT_SYSTIME:
                if isinstance(value, datetime):
                    # Convert to Windows FILETIME (100ns intervals since 1601-01-01)
                    timestamp = int((value.timestamp() + 11644473600) * 10000000)
                    return struct.pack('<Q', timestamp)
                return struct.pack('<Q', 0)
            elif prop_type == MapiPropertyType.PT_BINARY:
                if isinstance(value, bytes):
                    return value
                elif isinstance(value, str):
                    return value.encode('utf-8')
                return b''
            elif prop_type == MapiPropertyType.PT_BOOLEAN:
                return struct.pack('<B', 1 if value else 0)
            else:
                # Default to binary representation
                return str(value).encode('utf-8') if value else b''
        except Exception as e:
            logger.warning(f"Error serializing property type {prop_type}: {e}")
            return b''

class MapiMessageStore:
    """MAPI message store implementation"""
    
    def __init__(self):
        self.folders = self._initialize_folders()
    
    def _initialize_folders(self) -> Dict[str, MapiFolder]:
        """Initialize standard Exchange folder hierarchy"""
        folders = {}
        
        # Root folder
        root_folder = MapiFolder(
            folder_id="root",
            parent_id=None,
            display_name="Root",
            folder_type=MapiFolderType.FOLDER_ROOT,
            content_count=0,
            unread_count=0,
            entry_id=MapiEntryIdGenerator.generate_folder_entry_id("root"),
            properties={
                MapiPropertyTags.PR_DISPLAY_NAME: "Root",
                MapiPropertyTags.PR_FOLDER_TYPE: MapiFolderType.FOLDER_ROOT,
                MapiPropertyTags.PR_CONTENT_COUNT: 0,
                MapiPropertyTags.PR_CONTENT_UNREAD: 0
            }
        )
        folders["root"] = root_folder
        
        # Standard folders
        standard_folders = [
            ("inbox", "Inbox", "root"),
            ("sent_items", "Sent Items", "root"),
            ("outbox", "Outbox", "root"),
            ("drafts", "Drafts", "root"),
            ("deleted_items", "Deleted Items", "root"),
            ("junk_email", "Junk E-mail", "root"),
            ("calendar", "Calendar", "root"),
            ("contacts", "Contacts", "root"),
            ("tasks", "Tasks", "root"),
            ("notes", "Notes", "root")
        ]
        
        for folder_id, display_name, parent_id in standard_folders:
            folder = MapiFolder(
                folder_id=folder_id,
                parent_id=parent_id,
                display_name=display_name,
                folder_type=MapiFolderType.FOLDER_GENERIC,
                content_count=0,
                unread_count=0,
                entry_id=MapiEntryIdGenerator.generate_folder_entry_id(folder_id),
                properties={
                    MapiPropertyTags.PR_DISPLAY_NAME: display_name,
                    MapiPropertyTags.PR_FOLDER_TYPE: MapiFolderType.FOLDER_GENERIC,
                    MapiPropertyTags.PR_CONTENT_COUNT: 0,
                    MapiPropertyTags.PR_CONTENT_UNREAD: 0
                }
            )
            folders[folder_id] = folder
        
        return folders
    
    def get_folder_hierarchy(self) -> List[MapiFolder]:
        """Get folder hierarchy"""
        return list(self.folders.values())
    
    def get_folder_by_id(self, folder_id: str) -> Optional[MapiFolder]:
        """Get folder by ID"""
        return self.folders.get(folder_id)
    
    def get_folder_contents(self, folder_id: str, user_email: str) -> List[MapiMessage]:
        """Get folder contents (messages)"""
        try:
            db = SessionLocal()
            
            # Map folder IDs to our email filtering
            if folder_id == "inbox":
                emails = db.query(Email).filter(
                    Email.recipient == user_email,
                    Email.is_sent == False
                ).order_by(Email.created_at.desc()).limit(100).all()
            elif folder_id == "sent_items":
                emails = db.query(Email).filter(
                    Email.sender == user_email,
                    Email.is_sent == True
                ).order_by(Email.created_at.desc()).limit(100).all()
            else:
                # Other folders are empty for now
                emails = []
            
            messages = []
            for email in emails:
                properties = MapiPropertyConverter.email_to_mapi_properties(email)
                
                message = MapiMessage(
                    message_id=str(email.id),
                    folder_id=folder_id,
                    subject=email.subject or "",
                    sender_name=email.sender or "",
                    sender_email=email.sender or "",
                    recipient_name=email.recipient or "",
                    recipient_email=email.recipient or "",
                    body_text=email.body or "",
                    body_html=email.html_body or "",
                    creation_time=email.created_at or datetime.utcnow(),
                    last_modification_time=email.created_at or datetime.utcnow(),
                    message_size=len(email.body or "") + len(email.html_body or ""),
                    message_flags=MapiMessageFlags.MSGFLAG_READ if email.is_read else 0,
                    entry_id=properties[MapiPropertyTags.PR_ENTRYID],
                    properties=properties
                )
                messages.append(message)
            
            # Update folder counts
            if folder_id in self.folders:
                self.folders[folder_id].content_count = len(messages)
                unread_count = sum(1 for msg in messages if not (msg.message_flags & MapiMessageFlags.MSGFLAG_READ))
                self.folders[folder_id].unread_count = unread_count
                
                # Update properties
                self.folders[folder_id].properties[MapiPropertyTags.PR_CONTENT_COUNT] = len(messages)
                self.folders[folder_id].properties[MapiPropertyTags.PR_CONTENT_UNREAD] = unread_count
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting folder contents: {e}")
            return []
        finally:
            try:
                db.close()
            except:
                pass
    
    def get_message_by_id(self, message_id: str, user_email: str) -> Optional[MapiMessage]:
        """Get specific message by ID"""
        try:
            db = SessionLocal()
            email = db.query(Email).filter(Email.id == int(message_id)).first()
            
            if not email:
                return None
            
            # Check access permissions
            if email.recipient != user_email and email.sender != user_email:
                return None
            
            properties = MapiPropertyConverter.email_to_mapi_properties(email)
            
            # Determine folder
            folder_id = "inbox" if email.recipient == user_email else "sent_items"
            
            message = MapiMessage(
                message_id=str(email.id),
                folder_id=folder_id,
                subject=email.subject or "",
                sender_name=email.sender or "",
                sender_email=email.sender or "",
                recipient_name=email.recipient or "",
                recipient_email=email.recipient or "",
                body_text=email.body or "",
                body_html=email.html_body or "",
                creation_time=email.created_at or datetime.utcnow(),
                last_modification_time=email.created_at or datetime.utcnow(),
                message_size=len(email.body or "") + len(email.html_body or ""),
                message_flags=MapiMessageFlags.MSGFLAG_READ if email.is_read else 0,
                entry_id=properties[MapiPropertyTags.PR_ENTRYID],
                properties=properties
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Error getting message: {e}")
            return None
        finally:
            try:
                db.close()
            except:
                pass
    
    def serialize_folder_properties(self, folder: MapiFolder, requested_props: List[int] = None) -> bytes:
        """Serialize folder properties to binary format"""
        if requested_props is None:
            requested_props = list(folder.properties.keys())
        
        response = b''
        
        # Property count
        response += struct.pack('<I', len(requested_props))
        
        # Properties
        for prop_tag in requested_props:
            if prop_tag in folder.properties:
                value = folder.properties[prop_tag]
                prop_type = prop_tag & 0xFFFF
                
                # Property tag
                response += struct.pack('<I', prop_tag)
                
                # Property value
                prop_data = MapiPropertyConverter.serialize_property_value(prop_type, value)
                response += struct.pack('<I', len(prop_data))
                response += prop_data
            else:
                # Property not found - return error
                response += struct.pack('<I', prop_tag)
                response += struct.pack('<I', 0x8004010F)  # MAPI_E_NOT_FOUND
        
        return response
    
    def serialize_message_properties(self, message: MapiMessage, requested_props: List[int] = None) -> bytes:
        """Serialize message properties to binary format"""
        if requested_props is None:
            requested_props = list(message.properties.keys())
        
        response = b''
        
        # Property count
        response += struct.pack('<I', len(requested_props))
        
        # Properties
        for prop_tag in requested_props:
            if prop_tag in message.properties:
                value = message.properties[prop_tag]
                prop_type = prop_tag & 0xFFFF
                
                # Property tag
                response += struct.pack('<I', prop_tag)
                
                # Property value
                prop_data = MapiPropertyConverter.serialize_property_value(prop_type, value)
                response += struct.pack('<I', len(prop_data))
                response += prop_data
            else:
                # Property not found - return error
                response += struct.pack('<I', prop_tag)
                response += struct.pack('<I', 0x8004010F)  # MAPI_E_NOT_FOUND
        
        return response

# Global message store instance
message_store = MapiMessageStore()
