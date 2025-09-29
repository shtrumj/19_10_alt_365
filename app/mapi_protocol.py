"""
MAPI/HTTP Protocol Implementation

This module implements the Microsoft Exchange MAPI/HTTP protocol for Outlook Desktop connectivity.
MAPI/HTTP is a binary protocol that encapsulates MAPI RPC calls over HTTP.

Key Components:
- Binary protocol parsing/serialization
- Session management with context handles
- MAPI property system
- RPC operation handlers
- NSPI (Name Service Provider Interface) for address book

References:
- [MS-OXCMAPIHTTP]: Messaging Application Programming Interface (MAPI) Extensions for HTTP
- [MS-OXCRPC]: Wire Format Protocol
- [MS-OXCDATA]: Data Structures
"""

import struct
import uuid
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class MapiHttpRequestType(IntEnum):
    """MAPI/HTTP request types"""
    CONNECT = 0x00
    EXECUTE = 0x01
    DISCONNECT = 0x02
    NOTIFY_WAIT = 0x03

class MapiRpcOpNum(IntEnum):
    """MAPI RPC operation numbers"""
    EcDoConnect = 0x00
    EcDoDisconnect = 0x01
    EcDoRpc = 0x02
    EcGetMoreRpc = 0x03
    EcRRegisterPushNotification = 0x04
    EcRUnregisterPushNotification = 0x05
    EcDummyRpc = 0x06
    EcRGetDCName = 0x07
    EcRNetGetDCName = 0x08
    EcDoRpcExt = 0x09
    EcDoRpcExt2 = 0x0A
    EcDoConnectEx = 0x0B
    EcDoRpcExt2_2 = 0x0C

class MapiPropertyType(IntEnum):
    """MAPI property types"""
    PT_UNSPECIFIED = 0x0000
    PT_NULL = 0x0001
    PT_SHORT = 0x0002
    PT_LONG = 0x0003
    PT_FLOAT = 0x0004
    PT_DOUBLE = 0x0005
    PT_CURRENCY = 0x0006
    PT_APPTIME = 0x0007
    PT_ERROR = 0x000A
    PT_BOOLEAN = 0x000B
    PT_OBJECT = 0x000D
    PT_LONGLONG = 0x0014
    PT_STRING8 = 0x001E
    PT_UNICODE = 0x001F
    PT_SYSTIME = 0x0040
    PT_CLSID = 0x0048
    PT_BINARY = 0x0102
    PT_MV_SHORT = 0x1002
    PT_MV_LONG = 0x1003
    PT_MV_STRING8 = 0x101E
    PT_MV_UNICODE = 0x101F
    PT_MV_SYSTIME = 0x1040
    PT_MV_BINARY = 0x1102

# Common MAPI property tags
class MapiPropertyTags:
    PR_DISPLAY_NAME = 0x3001001F
    PR_EMAIL_ADDRESS = 0x3003001F
    PR_SUBJECT = 0x0037001F
    PR_MESSAGE_CLASS = 0x001A001F
    PR_CREATION_TIME = 0x30070040
    PR_LAST_MODIFICATION_TIME = 0x30080040
    PR_MESSAGE_SIZE = 0x0E080003
    PR_MESSAGE_FLAGS = 0x0E070003
    PR_BODY = 0x1000001F
    PR_BODY_HTML = 0x1013001F
    PR_SENDER_NAME = 0x0C1A001F
    PR_SENDER_EMAIL_ADDRESS = 0x0C1F001F
    PR_RECEIVED_BY_NAME = 0x0040001F
    PR_RECEIVED_BY_EMAIL_ADDRESS = 0x0076001F
    PR_ENTRYID = 0x0FFF0102
    PR_RECORD_KEY = 0x0FF90102
    PR_SEARCH_KEY = 0x300B0102
    PR_FOLDER_TYPE = 0x36010003
    PR_CONTENT_COUNT = 0x36020003
    PR_CONTENT_UNREAD = 0x36030003

@dataclass
class MapiContext:
    """MAPI session context"""
    session_id: str
    user_dn: str
    user_email: str
    context_handle: bytes
    created_at: datetime
    last_activity: datetime
    rpc_context: Dict[str, Any]

@dataclass
class MapiProperty:
    """MAPI property value"""
    tag: int
    prop_type: int
    value: Any

class MapiHttpRequest:
    """MAPI/HTTP request parser"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.request_type: Optional[int] = None
        self.flags: Optional[int] = None
        self.request_id: Optional[str] = None
        self.session_context_cookie: Optional[str] = None
        
    def parse(self) -> Dict[str, Any]:
        """Parse MAPI/HTTP request"""
        try:
            if len(self.data) < 12:
                raise ValueError("Request too short")
            
            # MAPI/HTTP Connect requests from Outlook have this format:
            # 8 bytes: Request header (usually zeros for Connect)
            # 4 bytes: Data length (little-endian)
            # N bytes: User DN string
            
            # Read request header (8 bytes)
            header = struct.unpack('<Q', self.data[0:8])[0]
            
            # Read data length (4 bytes)
            data_length = struct.unpack('<I', self.data[8:12])[0]
            
            self.offset = 12
            
            # Determine request type based on header and data pattern
            if header == 0 and data_length > 0:
                # Could be Connect (DN) or Execute (session cookie + RPC data)
                # Execute requests have: cookie_length + cookie + rpc_length + rpc_data
                # Connect requests have: dn_length + dn_string
                
                # Read the first 4 bytes to check the pattern
                if self.offset + 4 <= len(self.data):
                    first_length = struct.unpack('<I', self.data[self.offset:self.offset+4])[0]
                    
                    # Debug logging
                    logger.info(f"MAPI Parser Debug: data_length={data_length}, first_length={first_length}, total_len={len(self.data)}")
                    
                    # If first_length == 36 and total > 40, likely Execute (36-byte UUID + RPC data)
                    # If first_length < 200 and == data_length, likely Connect (DN only)
                    if first_length == 36 and data_length > 40:
                        # Execute request: session cookie (36 bytes) + RPC data
                        logger.info(f"MAPI Parser: Detected Execute request (session cookie)")
                        self.request_type = MapiHttpRequestType.EXECUTE
                        return self._parse_execute_request()
                    elif first_length == data_length and data_length < 200:
                        # Connect request: DN string only
                        logger.info(f"MAPI Parser: Detected Connect request (DN string)")
                        self.request_type = MapiHttpRequestType.CONNECT
                        return self._parse_outlook_connect_request(data_length)
                    else:
                        # Default to Execute for complex requests
                        logger.info(f"MAPI Parser: Defaulting to Execute request")
                        self.request_type = MapiHttpRequestType.EXECUTE
                        return self._parse_execute_request()
                else:
                    # Not enough data, assume Connect
                    self.request_type = MapiHttpRequestType.CONNECT
                    return self._parse_outlook_connect_request(data_length)
            elif header != 0:
                # This might be an Execute or other request type
                # Try to parse as traditional format
                self.request_type = (header & 0xFFFFFFFF)
                self.flags = ((header >> 32) & 0xFFFFFFFF)
                
                if self.request_type == MapiHttpRequestType.EXECUTE:
                    return self._parse_execute_request()
                elif self.request_type == MapiHttpRequestType.DISCONNECT:
                    return self._parse_disconnect_request()
                else:
                    return self._parse_connect_request()
            else:
                raise ValueError(f"Unable to determine request type from header: 0x{header:016x}")
                
        except Exception as e:
            logger.error(f"Error parsing MAPI request: {e}")
            raise
    
    def _parse_outlook_connect_request(self, data_length: int) -> Dict[str, Any]:
        """Parse Outlook-style Connect request with DN"""
        try:
            # Read the DN string
            if self.offset + data_length > len(self.data):
                raise ValueError("DN data extends beyond request")
            
            dn_data = self.data[self.offset:self.offset + data_length]
            
            # Try to decode as UTF-8, fallback to latin-1
            try:
                user_dn = dn_data.decode('utf-8').rstrip('\x00')
            except UnicodeDecodeError:
                user_dn = dn_data.decode('latin-1', errors='ignore').rstrip('\x00')
            
            logger.info(f"Parsed Connect request: DN='{user_dn}', length={data_length}")
            
            return {
                'type': 'connect',
                'user_dn': user_dn,
                'outlook_format': True
            }
            
        except Exception as e:
            logger.error(f"Error parsing Outlook Connect request: {e}")
            raise ValueError(f"Invalid Connect request: {e}")
    
    def _parse_connect_request(self) -> Dict[str, Any]:
        """Parse Connect request (traditional format)"""
        # User DN length (4 bytes)
        if self.offset + 4 > len(self.data):
            user_dn = ""
        else:
            dn_length = struct.unpack('<I', self.data[self.offset:self.offset+4])[0]
            self.offset += 4
            
            # User DN string
            if self.offset + dn_length > len(self.data):
                user_dn = ""
            else:
                user_dn = self.data[self.offset:self.offset+dn_length].decode('utf-8', errors='ignore')
                self.offset += dn_length
        
        return {
            'type': 'connect',
            'user_dn': user_dn,
            'flags': self.flags
        }
    
    def _parse_execute_request(self) -> Dict[str, Any]:
        """Parse Execute request"""
        # Session context cookie length (4 bytes)
        if self.offset + 4 > len(self.data):
            return {'type': 'execute', 'rpc_data': b'', 'session_cookie': ''}
            
        cookie_length = struct.unpack('<I', self.data[self.offset:self.offset+4])[0]
        self.offset += 4
        
        # Session context cookie
        session_cookie = ""
        if cookie_length > 0 and self.offset + cookie_length <= len(self.data):
            session_cookie = self.data[self.offset:self.offset+cookie_length].decode('utf-8', errors='ignore')
            self.offset += cookie_length
        
        # RPC data length (4 bytes)
        if self.offset + 4 > len(self.data):
            rpc_data = b''
        else:
            rpc_length = struct.unpack('<I', self.data[self.offset:self.offset+4])[0]
            self.offset += 4
            
            # RPC data
            if self.offset + rpc_length <= len(self.data):
                rpc_data = self.data[self.offset:self.offset+rpc_length]
            else:
                rpc_data = self.data[self.offset:]
        
        return {
            'type': 'execute',
            'session_cookie': session_cookie,
            'rpc_data': rpc_data
        }
    
    def _parse_disconnect_request(self) -> Dict[str, Any]:
        """Parse Disconnect request"""
        # Session context cookie length (4 bytes)
        if self.offset + 4 > len(self.data):
            return {'type': 'disconnect', 'session_cookie': ''}
            
        cookie_length = struct.unpack('<I', self.data[self.offset:self.offset+4])[0]
        self.offset += 4
        
        # Session context cookie
        session_cookie = ""
        if cookie_length > 0 and self.offset + cookie_length <= len(self.data):
            session_cookie = self.data[self.offset:self.offset+cookie_length].decode('utf-8', errors='ignore')
        
        return {
            'type': 'disconnect',
            'session_cookie': session_cookie
        }

class MapiHttpResponse:
    """MAPI/HTTP response builder"""
    
    def __init__(self):
        self.status_code = 0
        self.error_code = 0
        self.flags = 0
        self.data = b''
        
    def build_connect_response(self, session_cookie: str, poll_interval: int = 15) -> bytes:
        """Build Connect response with proper RPC context"""
        # Status code (4 bytes) - 0 = success
        response = struct.pack('<I', 0)
        
        # Error code (4 bytes) - 0 = no error
        response += struct.pack('<I', 0)
        
        # Flags (4 bytes)
        response += struct.pack('<I', 0)
        
        # Session context cookie length (4 bytes)
        cookie_bytes = session_cookie.encode('utf-8')
        response += struct.pack('<I', len(cookie_bytes))
        
        # Session context cookie
        response += cookie_bytes
        
        # Poll interval in milliseconds (4 bytes)
        response += struct.pack('<I', poll_interval * 1000)
        
        # Additional RPC context information that Outlook expects
        # RPC context handle (20 bytes) - UUID + attributes
        import uuid
        context_handle = uuid.uuid4().bytes + struct.pack('<I', 1)  # 16 bytes UUID + 4 bytes attributes
        response += context_handle
        
        # Server capabilities (4 bytes)
        # Bit flags indicating what the server supports
        server_caps = 0x00000001  # Basic MAPI operations supported
        response += struct.pack('<I', server_caps)
        
        # Maximum request size (4 bytes)
        max_request_size = 1048576  # 1MB
        response += struct.pack('<I', max_request_size)
        
        # Server version (4 bytes)
        server_version = 0x000F0000  # Exchange 2013 compatible
        response += struct.pack('<I', server_version)
        
        return response
    
    def build_execute_response(self, rpc_response_data: bytes) -> bytes:
        """Build Execute response"""
        # Status code (4 bytes) - 0 = success
        response = struct.pack('<I', 0)
        
        # Error code (4 bytes) - 0 = no error
        response += struct.pack('<I', 0)
        
        # Flags (4 bytes)
        response += struct.pack('<I', 0)
        
        # RPC response data length (4 bytes)
        response += struct.pack('<I', len(rpc_response_data))
        
        # RPC response data
        response += rpc_response_data
        
        return response
    
    def build_disconnect_response(self) -> bytes:
        """Build Disconnect response"""
        # Status code (4 bytes) - 0 = success
        response = struct.pack('<I', 0)
        
        # Error code (4 bytes) - 0 = no error
        response += struct.pack('<I', 0)
        
        # Flags (4 bytes)
        response += struct.pack('<I', 0)
        
        return response
    
    def build_error_response(self, error_code: int) -> bytes:
        """Build error response"""
        # Status code (4 bytes) - non-zero = error
        response = struct.pack('<I', error_code)
        
        # Error code (4 bytes)
        response += struct.pack('<I', error_code)
        
        # Flags (4 bytes)
        response += struct.pack('<I', 0)
        
        return response

class MapiRpcProcessor:
    """MAPI RPC operation processor"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.sessions: Dict[str, MapiContext] = {}
        self.rop_processors: Dict[str, Any] = {}  # Will be imported dynamically to avoid circular imports
    
    def process_rpc(self, session_cookie: str, rpc_data: bytes) -> bytes:
        """Process MAPI RPC operation"""
        try:
            if len(rpc_data) < 8:
                return self._build_rpc_error(0x80040111)  # MAPI_E_CALL_FAILED
            
            # Parse RPC header
            rpc_header_size = struct.unpack('<I', rpc_data[0:4])[0]
            rpc_opnum = struct.unpack('<I', rpc_data[4:8])[0]
            
            logger.info(f"Processing RPC operation {rpc_opnum} for session {session_cookie}")
            
            # Route to appropriate handler
            if rpc_opnum == MapiRpcOpNum.EcDoConnect:
                return self._handle_do_connect(rpc_data[8:])
            elif rpc_opnum == MapiRpcOpNum.EcDoRpc:
                return self._handle_do_rpc(session_cookie, rpc_data[8:])
            elif rpc_opnum == MapiRpcOpNum.EcDoDisconnect:
                return self._handle_do_disconnect(session_cookie)
            else:
                logger.warning(f"Unhandled RPC operation: {rpc_opnum}")
                return self._build_rpc_error(0x80040111)  # MAPI_E_CALL_FAILED
                
        except Exception as e:
            logger.error(f"Error processing RPC: {e}")
            return self._build_rpc_error(0x80040111)
    
    def _handle_do_connect(self, data: bytes) -> bytes:
        """Handle EcDoConnect RPC"""
        # For now, return success with minimal data
        response = struct.pack('<I', 0)  # Return code: success
        response += struct.pack('<I', 1000)  # Poll interval
        response += struct.pack('<I', 0)  # Retry count
        response += struct.pack('<I', 0)  # Retry delay
        response += struct.pack('<I', 0)  # DNS server name length
        response += struct.pack('<I', 0)  # DNS domain name length
        return response
    
    def _handle_do_rpc(self, session_cookie: str, data: bytes) -> bytes:
        """Handle EcDoRpc - core MAPI operations"""
        try:
            # Get session context
            session = session_manager.get_session(session_cookie)
            if not session:
                return self._build_rpc_error(0x80040111)
            
            # Get or create ROP processor for this session
            if session_cookie not in self.rop_processors:
                # Import here to avoid circular dependency
                from .mapi_rop import RopProcessor
                self.rop_processors[session_cookie] = RopProcessor(session.user_email)
            
            rop_processor = self.rop_processors[session_cookie]
            
            # Parse ROP buffer from RPC data
            if len(data) < 4:
                return self._build_rpc_error(0x80040111)
            
            # Skip RPC-specific headers and get to ROP buffer
            rop_buffer_offset = 0
            
            # Find ROP buffer in RPC data (simplified parsing)
            for offset in range(0, min(len(data) - 8, 100), 4):
                try:
                    # Look for ROP buffer header pattern
                    potential_size = struct.unpack('<H', data[offset:offset+2])[0]
                    potential_count = struct.unpack('<H', data[offset+2:offset+4])[0]
                    
                    # Reasonable ROP buffer size and count
                    if 8 <= potential_size <= len(data) - offset and 1 <= potential_count <= 50:
                        rop_buffer_offset = offset
                        break
                except:
                    continue
            
            rop_buffer = data[rop_buffer_offset:]
            
            # Process ROP buffer
            rop_response = rop_processor.process_rop_buffer(rop_buffer)
            
            # Build RPC response
            response = struct.pack('<I', 0)  # Return code: success
            response += struct.pack('<I', 0)  # Flags
            response += struct.pack('<I', len(rop_response))  # ROP response length
            response += rop_response
            
            return response
            
        except Exception as e:
            logger.error(f"Error in EcDoRpc: {e}")
            return self._build_rpc_error(0x80040111)
    
    def _handle_do_disconnect(self, session_cookie: str) -> bytes:
        """Handle EcDoDisconnect RPC"""
        if session_cookie in self.sessions:
            del self.sessions[session_cookie]
        
        # Clean up ROP processor
        if session_cookie in self.rop_processors:
            del self.rop_processors[session_cookie]
        
        response = struct.pack('<I', 0)  # Return code: success
        return response
    
    def _build_rpc_error(self, error_code: int) -> bytes:
        """Build RPC error response"""
        return struct.pack('<I', error_code)

class MapiSessionManager:
    """MAPI session management"""
    
    def __init__(self):
        self.sessions: Dict[str, MapiContext] = {}
    
    def create_session(self, user_dn: str, user_email: str) -> str:
        """Create new MAPI session"""
        session_id = str(uuid.uuid4())
        context_handle = uuid.uuid4().bytes
        
        context = MapiContext(
            session_id=session_id,
            user_dn=user_dn,
            user_email=user_email,
            context_handle=context_handle,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            rpc_context={}
        )
        
        self.sessions[session_id] = context
        logger.info(f"Created MAPI session {session_id} for user {user_email}")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[MapiContext]:
        """Get MAPI session"""
        return self.sessions.get(session_id)
    
    def update_activity(self, session_id: str):
        """Update session activity timestamp"""
        if session_id in self.sessions:
            self.sessions[session_id].last_activity = datetime.utcnow()
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 30):
        """Clean up expired sessions"""
        cutoff = datetime.utcnow().timestamp() - (timeout_minutes * 60)
        expired = [
            sid for sid, ctx in self.sessions.items()
            if ctx.last_activity.timestamp() < cutoff
        ]
        
        for sid in expired:
            del self.sessions[sid]
            logger.info(f"Cleaned up expired MAPI session {sid}")

# Global session manager instance
session_manager = MapiSessionManager()
