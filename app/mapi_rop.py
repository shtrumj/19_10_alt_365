"""
MAPI ROP (Remote Operations) Implementation

This module implements MAPI Remote Operations Protocol (ROP) which is used
within MAPI/HTTP Execute requests to perform actual mailbox operations.

Key ROP operations:
- RopLogon: Authenticate and establish mailbox context
- RopOpenFolder: Open folders (Inbox, Sent Items, etc.)
- RopGetContentsTable: Get folder contents (message list)
- RopQueryRows: Retrieve message/folder properties
- RopOpenMessage: Open specific messages
- RopCreateMessage: Create new messages
- RopSaveChangesMessage: Save message changes
- RopSubmitMessage: Send messages

References:
- [MS-OXCROPS]: Remote Operations (ROP) List and Encoding Protocol
- [MS-OXCFOLD]: Folder Object Protocol
- [MS-OXCMSG]: Message and Attachment Object Protocol
"""

import struct
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import IntEnum
import uuid

from .mapi_protocol import MapiProperty, MapiPropertyTags, MapiPropertyType
from .mapi_store import message_store, MapiFolder, MapiMessage, MapiPropertyConverter
from .database import SessionLocal, Email, User

logger = logging.getLogger(__name__)

class RopId(IntEnum):
    """ROP operation IDs"""
    RopLogon = 0xFE
    RopGetReceiveFolder = 0x27
    RopOpenFolder = 0x02
    RopCreateFolder = 0x1C
    RopGetContentsTable = 0x05
    RopGetHierarchyTable = 0x04
    RopQueryRows = 0x15
    RopSetColumns = 0x12
    RopSortTable = 0x13
    RopRestrict = 0x14
    RopOpenMessage = 0x03
    RopCreateMessage = 0x06
    RopSaveChangesMessage = 0x0C
    RopSubmitMessage = 0x32
    RopGetPropsSpecific = 0x07
    RopSetProps = 0x0A
    RopDeleteProps = 0x0B
    RopGetAttachmentTable = 0x21
    RopOpenAttach = 0x22
    RopCreateAttach = 0x23
    RopDeleteAttach = 0x24
    RopSaveChangesAttachment = 0x25
    RopRelease = 0x01

class LogonFlags(IntEnum):
    """RopLogon flags"""
    Private = 0x01
    Undercover = 0x02
    Ghosted = 0x04
    SpoolerProcess = 0x08

class OpenModeFlags(IntEnum):
    """Open mode flags"""
    ReadOnly = 0x00
    ReadWrite = 0x01
    BestAccess = 0x03

@dataclass
class RopRequest:
    """ROP request structure"""
    rop_id: int
    logon_id: int
    input_handle_index: int
    output_handle_index: int
    data: bytes

@dataclass
class RopResponse:
    """ROP response structure"""
    rop_id: int
    output_handle_index: int
    return_value: int
    data: bytes

class HandleManager:
    """Manages MAPI object handles"""
    
    def __init__(self):
        self.handles: Dict[int, Dict[str, Any]] = {}
        self.next_handle = 1
    
    def create_handle(self, object_type: str, object_data: Any) -> int:
        """Create new handle"""
        handle_id = self.next_handle
        self.next_handle += 1
        
        self.handles[handle_id] = {
            'type': object_type,
            'data': object_data,
            'created_at': struct.pack('<Q', int(uuid.uuid4().int & 0xFFFFFFFFFFFFFFFF))
        }
        
        return handle_id
    
    def get_handle(self, handle_id: int) -> Optional[Dict[str, Any]]:
        """Get handle data"""
        return self.handles.get(handle_id)
    
    def release_handle(self, handle_id: int):
        """Release handle"""
        if handle_id in self.handles:
            del self.handles[handle_id]

class RopProcessor:
    """Processes MAPI ROP operations"""
    
    def __init__(self, user_email: str):
        self.user_email = user_email
        self.handle_manager = HandleManager()
        self.logon_handle = None
        
    def process_rop_buffer(self, rop_buffer: bytes) -> bytes:
        """Process ROP buffer containing multiple ROP requests"""
        try:
            if len(rop_buffer) < 8:
                return self._build_error_response(0x80040111)
            
            # Parse ROP buffer header
            rop_size = struct.unpack('<H', rop_buffer[0:2])[0]
            rop_count = struct.unpack('<H', rop_buffer[2:4])[0]
            
            logger.info(f"Processing {rop_count} ROP operations, buffer size: {rop_size}")
            
            offset = 8  # Skip header
            responses = []
            
            # Process each ROP
            for i in range(rop_count):
                if offset >= len(rop_buffer):
                    break
                
                rop_request, consumed = self._parse_rop_request(rop_buffer[offset:])
                if rop_request is None:
                    break
                
                offset += consumed
                
                # Process individual ROP
                rop_response = self._process_single_rop(rop_request)
                responses.append(rop_response)
            
            # Build response buffer
            return self._build_rop_response_buffer(responses)
            
        except Exception as e:
            logger.error(f"Error processing ROP buffer: {e}")
            return self._build_error_response(0x80040111)
    
    def _parse_rop_request(self, data: bytes) -> Tuple[Optional[RopRequest], int]:
        """Parse single ROP request"""
        try:
            if len(data) < 4:
                return None, 0
            
            # ROP header: RopId (1), LogonId (1), InputHandleIndex (1), OutputHandleIndex (1)
            rop_id = struct.unpack('<B', data[0:1])[0]
            logon_id = struct.unpack('<B', data[1:2])[0]
            input_handle_index = struct.unpack('<B', data[2:3])[0]
            output_handle_index = struct.unpack('<B', data[3:4])[0]
            
            # Determine ROP data size based on ROP type
            rop_data_size = self._get_rop_data_size(rop_id, data[4:])
            
            if len(data) < 4 + rop_data_size:
                return None, 0
            
            rop_data = data[4:4+rop_data_size]
            
            request = RopRequest(
                rop_id=rop_id,
                logon_id=logon_id,
                input_handle_index=input_handle_index,
                output_handle_index=output_handle_index,
                data=rop_data
            )
            
            return request, 4 + rop_data_size
            
        except Exception as e:
            logger.error(f"Error parsing ROP request: {e}")
            return None, 0
    
    def _get_rop_data_size(self, rop_id: int, data: bytes) -> int:
        """Get ROP data size based on ROP type"""
        # This is simplified - real implementation would parse each ROP type properly
        if rop_id == RopId.RopLogon:
            return min(len(data), 100)  # Variable size, up to 100 bytes
        elif rop_id == RopId.RopOpenFolder:
            return min(len(data), 20)   # Folder ID + flags
        elif rop_id == RopId.RopGetContentsTable:
            return min(len(data), 4)    # Flags only
        elif rop_id == RopId.RopSetColumns:
            return min(len(data), 200)  # Variable size property list
        elif rop_id == RopId.RopQueryRows:
            return min(len(data), 8)    # Row count + flags
        elif rop_id == RopId.RopOpenMessage:
            return min(len(data), 20)   # Message ID + flags
        else:
            return min(len(data), 50)   # Default size
    
    def _process_single_rop(self, request: RopRequest) -> RopResponse:
        """Process single ROP operation"""
        try:
            logger.debug(f"Processing ROP {request.rop_id}")
            
            if request.rop_id == RopId.RopLogon:
                return self._handle_logon(request)
            elif request.rop_id == RopId.RopOpenFolder:
                return self._handle_open_folder(request)
            elif request.rop_id == RopId.RopGetContentsTable:
                return self._handle_get_contents_table(request)
            elif request.rop_id == RopId.RopSetColumns:
                return self._handle_set_columns(request)
            elif request.rop_id == RopId.RopQueryRows:
                return self._handle_query_rows(request)
            elif request.rop_id == RopId.RopOpenMessage:
                return self._handle_open_message(request)
            elif request.rop_id == RopId.RopGetPropsSpecific:
                return self._handle_get_props_specific(request)
            elif request.rop_id == RopId.RopGetHierarchyTable:
                return self._handle_get_hierarchy_table(request)
            elif request.rop_id == RopId.RopGetProps:
                return self._handle_get_props(request)
            elif request.rop_id == RopId.RopRelease:
                return self._handle_release(request)
            else:
                logger.warning(f"Unhandled ROP operation: {request.rop_id}")
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,  # MAPI_E_CALL_FAILED
                    data=b''
                )
                
        except Exception as e:
            logger.error(f"Error processing ROP {request.rop_id}: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_logon(self, request: RopRequest) -> RopResponse:
        """Handle RopLogon"""
        # Create logon handle
        logon_data = {
            'user_email': self.user_email,
            'mailbox_guid': uuid.uuid4().bytes,
            'store_state': 0
        }
        
        self.logon_handle = self.handle_manager.create_handle('logon', logon_data)
        
        # Build logon response
        response_data = b''
        response_data += struct.pack('<B', 0x01)  # LogonFlags: Private mailbox
        response_data += logon_data['mailbox_guid']  # Mailbox GUID
        response_data += struct.pack('<H', 0)  # Response flags
        response_data += struct.pack('<Q', 0)  # Mailbox DN size (empty)
        response_data += struct.pack('<Q', 0)  # Server DN size (empty)
        
        return RopResponse(
            rop_id=request.rop_id,
            output_handle_index=request.output_handle_index,
            return_value=0x00000000,  # Success
            data=response_data
        )
    
    def _handle_open_folder(self, request: RopRequest) -> RopResponse:
        """Handle RopOpenFolder"""
        try:
            # Parse folder ID from request data
            if len(request.data) >= 8:
                folder_id_bytes = request.data[0:8]
                # Convert to folder name - simplified mapping
                folder_map = {
                    b'\x01\x00\x00\x00\x00\x00\x00\x00': 'root',
                    b'\x02\x00\x00\x00\x00\x00\x00\x00': 'inbox',
                    b'\x03\x00\x00\x00\x00\x00\x00\x00': 'sent_items',
                    b'\x04\x00\x00\x00\x00\x00\x00\x00': 'outbox',
                    b'\x05\x00\x00\x00\x00\x00\x00\x00': 'drafts'
                }
                folder_name = folder_map.get(folder_id_bytes, 'inbox')
            else:
                folder_name = 'inbox'
            
            # Get folder from message store
            folder = message_store.get_folder_by_id(folder_name)
            if not folder:
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x8004010F,  # MAPI_E_NOT_FOUND
                    data=b''
                )
            
            # Create folder handle
            folder_handle = self.handle_manager.create_handle('folder', {
                'folder': folder,
                'folder_name': folder_name
            })
            
            # Build response
            response_data = b''
            response_data += struct.pack('<B', 1)  # HasRules
            response_data += struct.pack('<B', 0)  # IsGhosted
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in RopOpenFolder: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_get_contents_table(self, request: RopRequest) -> RopResponse:
        """Handle RopGetContentsTable"""
        try:
            # Get folder handle
            folder_handle_data = self.handle_manager.get_handle(request.input_handle_index)
            if not folder_handle_data or folder_handle_data['type'] != 'folder':
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,
                    data=b''
                )
            
            folder_name = folder_handle_data['data']['folder_name']
            
            # Get folder contents
            messages = message_store.get_folder_contents(folder_name, self.user_email)
            
            # Create contents table handle
            table_handle = self.handle_manager.create_handle('contents_table', {
                'messages': messages,
                'folder_name': folder_name,
                'columns': [],  # Will be set by SetColumns
                'current_row': 0
            })
            
            # Build response
            response_data = struct.pack('<I', len(messages))  # Row count
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in RopGetContentsTable: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_set_columns(self, request: RopRequest) -> RopResponse:
        """Handle RopSetColumns"""
        try:
            # Get table handle
            table_handle_data = self.handle_manager.get_handle(request.input_handle_index)
            if not table_handle_data or table_handle_data['type'] != 'contents_table':
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,
                    data=b''
                )
            
            # Parse column list from request
            if len(request.data) >= 2:
                column_count = struct.unpack('<H', request.data[0:2])[0]
                columns = []
                offset = 2
                
                for i in range(min(column_count, 20)):  # Limit columns
                    if offset + 4 <= len(request.data):
                        prop_tag = struct.unpack('<I', request.data[offset:offset+4])[0]
                        columns.append(prop_tag)
                        offset += 4
                
                # Update table handle with columns
                table_handle_data['data']['columns'] = columns
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,
                data=b'\x00'  # TableStatus: Complete
            )
            
        except Exception as e:
            logger.error(f"Error in RopSetColumns: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_query_rows(self, request: RopRequest) -> RopResponse:
        """Handle RopQueryRows"""
        try:
            # Get table handle
            table_handle_data = self.handle_manager.get_handle(request.input_handle_index)
            if not table_handle_data or table_handle_data['type'] != 'contents_table':
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,
                    data=b''
                )
            
            table_data = table_handle_data['data']
            messages = table_data['messages']
            columns = table_data['columns']
            current_row = table_data['current_row']
            
            # Parse request
            if len(request.data) >= 2:
                row_count = struct.unpack('<H', request.data[0:2])[0]
            else:
                row_count = 10
            
            # Limit row count
            row_count = min(row_count, 50)
            
            # Get requested rows
            end_row = min(current_row + row_count, len(messages))
            requested_messages = messages[current_row:end_row]
            
            # Build response
            response_data = b''
            response_data += struct.pack('<B', 0x00)  # Origin: Beginning
            response_data += struct.pack('<H', len(requested_messages))  # Row count
            
            # Serialize each row
            for message in requested_messages:
                row_data = self._serialize_message_row(message, columns)
                response_data += struct.pack('<H', len(row_data))
                response_data += row_data
            
            # Update current row
            table_data['current_row'] = end_row
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in RopQueryRows: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_open_message(self, request: RopRequest) -> RopResponse:
        """Handle RopOpenMessage"""
        # For now, return success but don't implement full message opening
        return RopResponse(
            rop_id=request.rop_id,
            output_handle_index=request.output_handle_index,
            return_value=0x00000000,
            data=b'\x01\x00'  # HasNamedProperties, SubjectPrefix
        )
    
    def _handle_get_props_specific(self, request: RopRequest) -> RopResponse:
        """Handle RopGetPropsSpecific"""
        # Return empty property list for now
        response_data = b''
        response_data += struct.pack('<B', 0x00)  # Layout: Fixed
        response_data += struct.pack('<H', 0)     # Property count
        
        return RopResponse(
            rop_id=request.rop_id,
            output_handle_index=request.output_handle_index,
            return_value=0x00000000,
            data=response_data
        )
    
    def _handle_get_hierarchy_table(self, request: RopRequest) -> RopResponse:
        """Handle RopGetHierarchyTable - get folder hierarchy table"""
        try:
            # Create a table handle for folder hierarchy
            table_handle = self.handle_manager.allocate_handle("hierarchy_table")
            
            # Get folder hierarchy from message store
            from .mapi_store import message_store
            folders = message_store.get_folder_hierarchy()
            
            # Store folder data in handle
            self.handle_manager.set_handle_data(table_handle, {
                "type": "hierarchy_table",
                "folders": folders,
                "position": 0
            })
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,  # Success
                data=struct.pack('<I', len(folders))  # Row count
            )
        except Exception as e:
            logger.error(f"Error in RopGetHierarchyTable: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_get_props(self, request: RopRequest) -> RopResponse:
        """Handle RopGetProps - get object properties"""
        try:
            # Get handle data
            handle_data = self.handle_manager.get_handle_data(request.input_handle_index)
            if not handle_data:
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,
                    data=b''
                )
            
            # Parse property tags from request data
            if len(request.data) < 4:
                return RopResponse(
                    rop_id=request.rop_id,
                    output_handle_index=request.output_handle_index,
                    return_value=0x80040111,
                    data=b''
                )
            
            prop_count = struct.unpack('<I', request.data[0:4])[0]
            requested_props = []
            offset = 4
            
            for i in range(min(prop_count, 50)):  # Limit to prevent abuse
                if offset + 4 <= len(request.data):
                    prop_tag = struct.unpack('<I', request.data[offset:offset+4])[0]
                    requested_props.append(prop_tag)
                    offset += 4
            
            # Get properties based on handle type
            if handle_data.get("type") == "folder":
                folder = handle_data.get("folder")
                if folder:
                    from .mapi_store import message_store
                    response_data = message_store.serialize_folder_properties(folder, requested_props)
                else:
                    response_data = b'\x00\x00\x00\x00'  # No properties
            elif handle_data.get("type") == "message":
                message = handle_data.get("message")
                if message:
                    from .mapi_store import message_store
                    response_data = message_store.serialize_message_properties(message, requested_props)
                else:
                    response_data = b'\x00\x00\x00\x00'  # No properties
            else:
                # Default empty response
                response_data = b'\x00\x00\x00\x00'
            
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x00000000,
                data=response_data
            )
        except Exception as e:
            logger.error(f"Error in RopGetProps: {e}")
            return RopResponse(
                rop_id=request.rop_id,
                output_handle_index=request.output_handle_index,
                return_value=0x80040111,
                data=b''
            )
    
    def _handle_release(self, request: RopRequest) -> RopResponse:
        """Handle RopRelease"""
        self.handle_manager.release_handle(request.input_handle_index)
        
        return RopResponse(
            rop_id=request.rop_id,
            output_handle_index=request.output_handle_index,
            return_value=0x00000000,
            data=b''
        )
    
    def _serialize_message_row(self, message: MapiMessage, columns: List[int]) -> bytes:
        """Serialize message row data"""
        row_data = b''
        
        for prop_tag in columns:
            if prop_tag in message.properties:
                value = message.properties[prop_tag]
                prop_type = prop_tag & 0xFFFF
                
                # Property exists
                row_data += struct.pack('<B', 0x00)  # No error
                
                # Serialize value
                prop_data = MapiPropertyConverter.serialize_property_value(prop_type, value)
                if prop_type in [MapiPropertyType.PT_UNICODE, MapiPropertyType.PT_STRING8, MapiPropertyType.PT_BINARY]:
                    # Variable length properties
                    row_data += struct.pack('<H', len(prop_data))
                    row_data += prop_data
                else:
                    # Fixed length properties
                    row_data += prop_data
            else:
                # Property not found
                row_data += struct.pack('<B', 0x0F)  # MAPI_E_NOT_FOUND
        
        return row_data
    
    def _build_rop_response_buffer(self, responses: List[RopResponse]) -> bytes:
        """Build ROP response buffer"""
        # Calculate total size
        total_size = 8  # Header
        for response in responses:
            total_size += 4 + len(response.data)  # ROP header + data
        
        # Build buffer
        buffer = b''
        buffer += struct.pack('<H', total_size)  # ROP buffer size
        buffer += struct.pack('<H', len(responses))  # ROP count
        buffer += struct.pack('<I', 0)  # Reserved
        
        # Add responses
        for response in responses:
            buffer += struct.pack('<B', response.rop_id)
            buffer += struct.pack('<B', response.output_handle_index)
            buffer += struct.pack('<I', response.return_value)
            buffer += response.data
        
        return buffer
    
    def _build_error_response(self, error_code: int) -> bytes:
        """Build error response"""
        buffer = b''
        buffer += struct.pack('<H', 12)  # Buffer size
        buffer += struct.pack('<H', 1)   # ROP count
        buffer += struct.pack('<I', 0)   # Reserved
        buffer += struct.pack('<B', 0xFF)  # Error ROP
        buffer += struct.pack('<B', 0)   # Output handle index
        buffer += struct.pack('<I', error_code)  # Error code
        
        return buffer
