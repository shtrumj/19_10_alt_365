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
                    elif data_length >= 16:
                        # Likely Connect request with structured payload
                        logger.info("MAPI Parser: Detected Connect request (structured)")
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
    
    def _read_uint32(self, blob: bytes, offset: int) -> Tuple[int, int]:
        if offset + 4 > len(blob):
            raise ValueError("Truncated MAPI request payload")
        value = struct.unpack_from('<I', blob, offset)[0]
        return value, offset + 4

    def _read_counted_string(self, blob: bytes, offset: int) -> Tuple[str, int]:
        length, offset = self._read_uint32(blob, offset)
        if offset + length > len(blob):
            raise ValueError("String exceeds payload length")
        raw = blob[offset : offset + length]
        offset += length
        return raw.decode('utf-8', errors='ignore').rstrip('\x00'), offset

    def _parse_outlook_connect_request(self, data_length: int) -> Dict[str, Any]:
        """Parse Outlook-style Connect request (EcDoConnectEx)."""
        data = self.data[self.offset : self.offset + data_length]
        offset = 0

        try:
            user_dn, offset = self._read_counted_string(data, offset)
            flags, offset = self._read_uint32(data, offset)
            cpid, offset = self._read_uint32(data, offset)
            lcid_string, offset = self._read_uint32(data, offset)
            lcid_sort, offset = self._read_uint32(data, offset)
            aux_len, offset = self._read_uint32(data, offset)
            if offset + aux_len > len(data):
                raise ValueError("Auxiliary buffer exceeds payload length")
            aux_data = data[offset : offset + aux_len]
            offset += aux_len

            logger.info(
                "Parsed Connect request: dn=%s flags=0x%08x cpid=%d lcid_string=%d",
                user_dn,
                flags,
                cpid,
                lcid_string,
            )
            self.offset += data_length

            return {
                "type": "connect",
                "user_dn": user_dn,
                "flags": flags,
                "cpid": cpid,
                "lcid_string": lcid_string,
                "lcid_sort": lcid_sort,
                "aux_in": aux_data,
            }

        except Exception as exc:
            logger.error("Error parsing Connect request: %s", exc)
            raise ValueError(f"Invalid Connect request: {exc}")
    
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
        """Parse Execute (EcDoRpcExt2) request."""
        # Remaining payload is execute structure
        remaining = self.data[self.offset :]
        offset = 0

        try:
            flags, offset = self._read_uint32(remaining, offset)
            rpc_length, offset = self._read_uint32(remaining, offset)
            if offset + rpc_length > len(remaining):
                raise ValueError("RPC payload truncated")
            rpc_data = remaining[offset : offset + rpc_length]
            offset += rpc_length

            max_response, offset = self._read_uint32(remaining, offset)
            aux_len, offset = self._read_uint32(remaining, offset)
            if offset + aux_len > len(remaining):
                raise ValueError("Auxiliary payload truncated")
            aux_data = remaining[offset : offset + aux_len]
            offset += aux_len

            self.offset += offset

            return {
                "type": "execute",
                "flags": flags,
                "rpc_data": rpc_data,
                "max_response": max_response,
                "aux_in": aux_data,
            }

        except Exception as exc:
            logger.error("Error parsing Execute request: %s", exc)
            raise ValueError(f"Invalid Execute request: {exc}")
    
    def _parse_disconnect_request(self) -> Dict[str, Any]:
        """Parse Disconnect request"""
        remaining = self.data[self.offset :]
        offset = 0
        try:
            aux_len, offset = self._read_uint32(remaining, offset)
            if offset + aux_len > len(remaining):
                raise ValueError("Auxiliary payload truncated")
            aux_data = remaining[offset : offset + aux_len]
            offset += aux_len

            self.offset += offset

            return {
                "type": "disconnect",
                "aux_in": aux_data,
            }
        except Exception as exc:
            logger.error("Error parsing Disconnect request: %s", exc)
            raise ValueError(f"Invalid Disconnect request: {exc}")

class MapiHttpResponse:
    """MAPI/HTTP response builder"""

    def __init__(self):
        self.status_code = 0
        self.error_code = 0
        self.flags = 0
        self.data = b''

    def _pack_ascii(self, value: str) -> bytes:
        data = value.encode("utf-8")
        # Include terminating null as per RPC EXT pack format
        return struct.pack("<I", len(data) + 1) + data + b"\x00"

    def _pack_utf16(self, value: str) -> bytes:
        data = value.encode("utf-16le")
        return struct.pack("<I", len(data) + 2) + data + b"\x00\x00"

    def build_connect_response(
        self,
        *,
        dn_prefix: str,
        display_name: str,
        max_polls: int = 60,
        max_retry: int = 0,
        retry_delay: int = 0,
        aux_out: bytes = b"",
    ) -> bytes:
        """Build Connect response (EcDoConnectEx)."""

        response = bytearray()
        response += struct.pack("<I", 0)  # status
        response += struct.pack("<I", 0)  # result (ecSuccess)
        response += struct.pack("<I", max_polls)
        response += struct.pack("<I", max_retry)
        response += struct.pack("<I", retry_delay)
        response += self._pack_ascii(dn_prefix or "")
        response += self._pack_utf16(display_name or "Mailbox")
        response += struct.pack("<I", len(aux_out))
        response += aux_out
        return bytes(response)

    def build_execute_response(
        self,
        rpc_response_data: bytes,
        *,
        flags: int = 0,
        aux_out: bytes = b"",
    ) -> bytes:
        """Build Execute response (EcDoRpcExt2)."""

        response = bytearray()
        response += struct.pack("<I", 0)  # status
        response += struct.pack("<I", 0)  # result
        response += struct.pack("<I", flags)
        response += struct.pack("<I", len(rpc_response_data))
        response += rpc_response_data
        response += struct.pack("<I", len(aux_out))
        response += aux_out
        return bytes(response)

    def build_disconnect_response(self, *, status: int = 0, result: int = 0) -> bytes:
        """Build Disconnect response."""

        response = bytearray()
        response += struct.pack("<I", status)
        response += struct.pack("<I", result)
        response += struct.pack("<I", 0)  # cbAuxOut
        return bytes(response)

    def build_error_response(self, error_code: int) -> bytes:
        """Build error response"""
        # Status code (4 bytes) - non-zero = error
        response = bytearray()
        response += struct.pack("<I", error_code)
        response += struct.pack("<I", error_code)
        response += struct.pack("<I", 0)
        return bytes(response)

class MapiRpcProcessor:
    """MAPI RPC operation processor"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.sessions: Dict[str, MapiContext] = {}
        self.rop_processors: Dict[str, Any] = {}  # Will be imported dynamically to avoid circular imports
    
    def process_rpc(
        self,
        session_cookie: str,
        rpc_data: bytes,
        *,
        max_response_size: int = 0,
        request_flags: int = 0,
        aux_in: Optional[bytes] = None,
    ) -> bytes:
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
                return self._handle_do_rpc(
                    session_cookie,
                    rpc_data[8:],
                    max_response_size=max_response_size,
                    request_flags=request_flags,
                    aux_in=aux_in or b"",
                )
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
    
    def _handle_do_rpc(
        self,
        session_cookie: str,
        data: bytes,
        *,
        max_response_size: int = 0,
        request_flags: int = 0,
        aux_in: bytes = b"",
    ) -> bytes:
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
            if max_response_size and len(rop_response) > max_response_size:
                rop_response = rop_response[:max_response_size]
            
            # Build RPC response
            response = bytearray()
            response += struct.pack('<I', 0)  # Return code: success
            response += struct.pack('<I', request_flags & 0xFFFFFFFF)
            response += struct.pack('<I', len(rop_response))
            response += rop_response
            response += struct.pack('<I', 0)  # cbAuxOut

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

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

# Global session manager instance
session_manager = MapiSessionManager()
