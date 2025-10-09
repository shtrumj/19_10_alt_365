#!/usr/bin/env python3
"""
Test script for MAPI/HTTP protocol implementation

This script tests the complete MAPI/HTTP protocol stack:
1. MAPI/HTTP Connect request
2. MAPI RPC operations (Logon, OpenFolder, GetContentsTable, QueryRows)
3. MAPI/HTTP Execute requests
4. MAPI/HTTP Disconnect request

Usage: python test_scripts/test_mapi_protocol.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import requests
import struct
import json
from typing import Dict, Any

def build_mapi_connect_request(user_dn: str = "/o=365 Email System/ou=Exchange Administrative Group/cn=Recipients/cn=yonatan") -> bytes:
    """Build MAPI/HTTP Connect request"""
    request_data = b''
    
    # Request type (4 bytes) - Connect = 0x00
    request_data += struct.pack('<I', 0x00)
    
    # Flags (4 bytes)
    request_data += struct.pack('<I', 0x00)
    
    # User DN length (4 bytes)
    user_dn_bytes = user_dn.encode('utf-8')
    request_data += struct.pack('<I', len(user_dn_bytes))
    
    # User DN
    request_data += user_dn_bytes
    
    return request_data

def build_mapi_execute_request(session_cookie: str, rop_buffer: bytes) -> bytes:
    """Build MAPI/HTTP Execute request"""
    request_data = b''
    
    # Request type (4 bytes) - Execute = 0x01
    request_data += struct.pack('<I', 0x01)
    
    # Flags (4 bytes)
    request_data += struct.pack('<I', 0x00)
    
    # Session context cookie length (4 bytes)
    cookie_bytes = session_cookie.encode('utf-8')
    request_data += struct.pack('<I', len(cookie_bytes))
    
    # Session context cookie
    request_data += cookie_bytes
    
    # RPC data length (4 bytes)
    request_data += struct.pack('<I', len(rop_buffer))
    
    # RPC data (contains ROP buffer)
    request_data += rop_buffer
    
    return request_data

def build_mapi_disconnect_request(session_cookie: str) -> bytes:
    """Build MAPI/HTTP Disconnect request"""
    request_data = b''
    
    # Request type (4 bytes) - Disconnect = 0x02
    request_data += struct.pack('<I', 0x02)
    
    # Flags (4 bytes)
    request_data += struct.pack('<I', 0x00)
    
    # Session context cookie length (4 bytes)
    cookie_bytes = session_cookie.encode('utf-8')
    request_data += struct.pack('<I', len(cookie_bytes))
    
    # Session context cookie
    request_data += cookie_bytes
    
    return request_data

def build_rpc_buffer(rop_operations: list) -> bytes:
    """Build RPC buffer containing ROP operations"""
    # RPC header
    rpc_data = b''
    rpc_data += struct.pack('<I', 0)  # RPC header size (placeholder)
    rpc_data += struct.pack('<I', 2)  # RPC opnum: EcDoRpc
    
    # ROP buffer
    rop_buffer = b''
    
    # ROP buffer header
    total_rop_size = 8  # Header size
    for rop_data in rop_operations:
        total_rop_size += len(rop_data)
    
    rop_buffer += struct.pack('<H', total_rop_size)  # ROP buffer size
    rop_buffer += struct.pack('<H', len(rop_operations))  # ROP count
    rop_buffer += struct.pack('<I', 0)  # Reserved
    
    # Add ROP operations
    for rop_data in rop_operations:
        rop_buffer += rop_data
    
    rpc_data += rop_buffer
    
    return rpc_data

def build_rop_logon() -> bytes:
    """Build RopLogon operation"""
    rop_data = b''
    rop_data += struct.pack('<B', 0xFE)  # RopId: RopLogon
    rop_data += struct.pack('<B', 0x00)  # LogonId
    rop_data += struct.pack('<B', 0xFF)  # InputHandleIndex (no input)
    rop_data += struct.pack('<B', 0x00)  # OutputHandleIndex
    
    # RopLogon specific data
    rop_data += struct.pack('<B', 0x01)  # LogonFlags: Private
    rop_data += struct.pack('<I', 0x00)  # OpenFlags
    rop_data += struct.pack('<I', 0x00)  # StoreState
    rop_data += struct.pack('<H', 0)     # EssdnSize (empty)
    
    return rop_data

def build_rop_open_folder(folder_id: int = 2) -> bytes:
    """Build RopOpenFolder operation"""
    rop_data = b''
    rop_data += struct.pack('<B', 0x02)  # RopId: RopOpenFolder
    rop_data += struct.pack('<B', 0x00)  # LogonId
    rop_data += struct.pack('<B', 0x00)  # InputHandleIndex (logon handle)
    rop_data += struct.pack('<B', 0x01)  # OutputHandleIndex (folder handle)
    
    # RopOpenFolder specific data
    rop_data += struct.pack('<Q', folder_id)  # FolderId (inbox = 2)
    rop_data += struct.pack('<B', 0x00)  # OpenModeFlags
    
    return rop_data

def build_rop_get_contents_table() -> bytes:
    """Build RopGetContentsTable operation"""
    rop_data = b''
    rop_data += struct.pack('<B', 0x05)  # RopId: RopGetContentsTable
    rop_data += struct.pack('<B', 0x00)  # LogonId
    rop_data += struct.pack('<B', 0x01)  # InputHandleIndex (folder handle)
    rop_data += struct.pack('<B', 0x02)  # OutputHandleIndex (table handle)
    
    # RopGetContentsTable specific data
    rop_data += struct.pack('<B', 0x00)  # TableFlags
    
    return rop_data

def build_rop_set_columns() -> bytes:
    """Build RopSetColumns operation"""
    rop_data = b''
    rop_data += struct.pack('<B', 0x12)  # RopId: RopSetColumns
    rop_data += struct.pack('<B', 0x00)  # LogonId
    rop_data += struct.pack('<B', 0x02)  # InputHandleIndex (table handle)
    rop_data += struct.pack('<B', 0xFF)  # OutputHandleIndex (no output)
    
    # Column list
    columns = [
        0x0FFF0102,  # PR_ENTRYID
        0x0037001F,  # PR_SUBJECT
        0x0C1A001F,  # PR_SENDER_NAME
        0x30070040,  # PR_CREATION_TIME
        0x0E080003,  # PR_MESSAGE_SIZE
    ]
    
    rop_data += struct.pack('<B', 0x00)  # SetColumnsFlags
    rop_data += struct.pack('<H', len(columns))  # PropertyTagCount
    
    for prop_tag in columns:
        rop_data += struct.pack('<I', prop_tag)
    
    return rop_data

def build_rop_query_rows(row_count: int = 10) -> bytes:
    """Build RopQueryRows operation"""
    rop_data = b''
    rop_data += struct.pack('<B', 0x15)  # RopId: RopQueryRows
    rop_data += struct.pack('<B', 0x00)  # LogonId
    rop_data += struct.pack('<B', 0x02)  # InputHandleIndex (table handle)
    rop_data += struct.pack('<B', 0xFF)  # OutputHandleIndex (no output)
    
    # RopQueryRows specific data
    rop_data += struct.pack('<B', 0x00)  # QueryRowsFlags
    rop_data += struct.pack('<B', 0x00)  # ForwardRead
    rop_data += struct.pack('<H', row_count)  # RowCount
    
    return rop_data

def parse_mapi_response(response_data: bytes) -> Dict[str, Any]:
    """Parse MAPI/HTTP response"""
    if len(response_data) < 12:
        return {"error": "Response too short"}
    
    status_code = struct.unpack('<I', response_data[0:4])[0]
    error_code = struct.unpack('<I', response_data[4:8])[0]
    flags = struct.unpack('<I', response_data[8:12])[0]
    
    result = {
        "status_code": status_code,
        "error_code": error_code,
        "flags": flags,
        "data": response_data[12:].hex() if len(response_data) > 12 else ""
    }
    
    return result

def test_mapi_connect():
    """Test MAPI/HTTP Connect"""
    print("=== Testing MAPI/HTTP Connect ===")
    
    try:
        connect_request = build_mapi_connect_request()
        
        response = requests.post(
            "https://owa.shtrum.com/mapi/emsmdb",
            data=connect_request,
            headers={
                "Content-Type": "application/mapi-http",
                "User-Agent": "Test-MAPI-Client/1.0"
            },
            timeout=30,
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            parsed = parse_mapi_response(response.content)
            print(f"Response: {json.dumps(parsed, indent=2)}")
            
            # Extract session cookie from headers
            session_cookie = response.headers.get('X-SessionCookie', '')
            print(f"Session Cookie: {session_cookie}")
            
            return session_cookie
        else:
            print(f"Connect failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Connect error: {e}")
        return None

def test_mapi_execute(session_cookie: str):
    """Test MAPI/HTTP Execute with ROP operations"""
    print("\n=== Testing MAPI/HTTP Execute ===")
    
    try:
        # Build ROP operations for typical Outlook workflow
        rop_operations = [
            build_rop_logon(),
            build_rop_open_folder(2),  # Open Inbox
            build_rop_get_contents_table(),
            build_rop_set_columns(),
            build_rop_query_rows(5)
        ]
        
        rpc_buffer = build_rpc_buffer(rop_operations)
        execute_request = build_mapi_execute_request(session_cookie, rpc_buffer)
        
        response = requests.post(
            "https://owa.shtrum.com/mapi/emsmdb",
            data=execute_request,
            headers={
                "Content-Type": "application/mapi-http",
                "User-Agent": "Test-MAPI-Client/1.0"
            },
            timeout=30,
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            parsed = parse_mapi_response(response.content)
            print(f"Response: {json.dumps(parsed, indent=2)}")
            return True
        else:
            print(f"Execute failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Execute error: {e}")
        return False

def test_mapi_disconnect(session_cookie: str):
    """Test MAPI/HTTP Disconnect"""
    print("\n=== Testing MAPI/HTTP Disconnect ===")
    
    try:
        disconnect_request = build_mapi_disconnect_request(session_cookie)
        
        response = requests.post(
            "https://owa.shtrum.com/mapi/emsmdb",
            data=disconnect_request,
            headers={
                "Content-Type": "application/mapi-http",
                "User-Agent": "Test-MAPI-Client/1.0"
            },
            timeout=30,
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            parsed = parse_mapi_response(response.content)
            print(f"Response: {json.dumps(parsed, indent=2)}")
            return True
        else:
            print(f"Disconnect failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Disconnect error: {e}")
        return False

def main():
    """Run complete MAPI/HTTP protocol test"""
    print("MAPI/HTTP Protocol Test Suite")
    print("=" * 50)
    
    # Disable SSL warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Test Connect
    session_cookie = test_mapi_connect()
    if not session_cookie:
        print("❌ Connect test failed")
        return False
    
    print("✅ Connect test passed")
    
    # Test Execute
    execute_success = test_mapi_execute(session_cookie)
    if not execute_success:
        print("❌ Execute test failed")
    else:
        print("✅ Execute test passed")
    
    # Test Disconnect
    disconnect_success = test_mapi_disconnect(session_cookie)
    if not disconnect_success:
        print("❌ Disconnect test failed")
    else:
        print("✅ Disconnect test passed")
    
    print("\n" + "=" * 50)
    if execute_success and disconnect_success:
        print("🎉 All MAPI/HTTP tests passed!")
        return True
    else:
        print("⚠️  Some tests failed - check logs for details")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
