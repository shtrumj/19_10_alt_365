from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from ..diagnostic_logger import (
    _write_json_line, outlook_diagnostics, log_mapi_request, 
    log_outlook_connection_issue
)
from ..mapi_protocol import (
    MapiHttpRequest, MapiHttpResponse, MapiRpcProcessor, 
    session_manager, MapiHttpRequestType
)
from ..mapi_store import message_store
from ..database import SessionLocal, User
import os
import logging
import uuid
import base64

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mapi", tags=["mapihttp"])

# Also create a router without prefix for root-level MAPI endpoints
root_router = APIRouter(tags=["mapihttp-root"])

def log_mapi(event: str, details: dict):
    _write_json_line("web/mapi/mapi.log", {"event": event, **(details or {})})

# Initialize RPC processor
rpc_processor = None

def get_rpc_processor():
    global rpc_processor
    if rpc_processor is None:
        db = SessionLocal()
        rpc_processor = MapiRpcProcessor(db)
    return rpc_processor

@router.post("/emsmdb")
async def mapi_emsmdb(request: Request):
    """MAPI/HTTP EMSMDB endpoint - handles mailbox operations"""
    body = await request.body()
    ua = request.headers.get("User-Agent", "")
    content_type = request.headers.get("Content-Type", "")
    auth_header = request.headers.get("Authorization", "")
    
    # Start enhanced diagnostic logging
    request_id = str(uuid.uuid4())
    
    # Enhanced logging for Outlook debugging
    log_mapi("emsmdb", {
        "request_id": request_id,
        "len": len(body), 
        "ua": ua, 
        "content_type": content_type,
        "method": "POST",
        "headers": dict(request.headers),
        "client_ip": request.client.host if request.client else "unknown",
        "has_auth": bool(auth_header),
        "auth_type": auth_header.split(" ")[0] if " " in auth_header else auth_header[:10] if auth_header else "none"
    })
    
    # Log this as an Outlook phase
    outlook_diagnostics.log_outlook_phase("mapi_request_received", {
        "request_id": request_id,
        "content_length": len(body),
        "has_authentication": bool(auth_header),
        "user_agent": ua
    })
    
    try:
        # Enhanced authentication handling
        if auth_header:
            auth_type = auth_header.split(" ")[0] if " " in auth_header else "unknown"
            log_mapi("auth_received", {
                "request_id": request_id,
                "auth_type": auth_type,
                "has_credentials": len(auth_header) > 10
            })
            
            # Log authentication attempt
            outlook_diagnostics.log_authentication_flow(auth_type, "credentials_received", True, {
                "request_id": request_id,
                "user_agent": ua
            })
            
            # Decode Basic auth for logging (without exposing password)
            if auth_type.lower() == "basic" and " " in auth_header:
                try:
                    encoded = auth_header.split(" ")[1]
                    decoded = base64.b64decode(encoded).decode('utf-8')
                    username = decoded.split(":")[0] if ":" in decoded else "unknown"
                    log_mapi("basic_auth_user", {"request_id": request_id, "username": username})
                except:
                    pass
                    
        elif len(body) == 0:
            # Empty request without auth - send NTLM challenge
            log_mapi("auth_challenge", {
                "request_id": request_id,
                "reason": "no_auth_header",
                "challenge_type": "NTLM"
            })
            
            outlook_diagnostics.log_authentication_flow("NTLM", "challenge_sent", True, {
                "request_id": request_id,
                "reason": "no_auth_header"
            })
            
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": "NTLM",
                    "Content-Type": "application/mapi-http",
                    "X-ClientInfo": "365-Email-System/1.0",
                    "X-RequestId": request_id
                }
            )
        
        # Log the raw request for debugging
        log_mapi("raw_request", {
            "length": len(body),
            "hex_preview": body[:32].hex() if len(body) > 0 else "",
            "auth_type": auth_header.split(" ")[0] if " " in auth_header else "none"
        })
        
        # For now, accept any request with body without full authentication validation
        # Real implementation would validate NTLM/Kerberos tokens
        
        # Handle NTLM authentication flow properly
        if auth_header and auth_header.startswith("NTLM") and len(body) == 0:
            # This is an NTLM negotiation request - send Type 2 challenge
            log_mapi("ntlm_negotiation", {
                "request_id": request_id,
                "stage": "type1_received",
                "body_length": len(body)
            })
            
            outlook_diagnostics.log_authentication_flow("NTLM", "type1_received", True, {
                "request_id": request_id,
                "next_step": "send_type2_challenge"
            })
            
            # For now, we'll send a simple NTLM Type 2 challenge response
            # In a real implementation, this would be a proper NTLM Type 2 message
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": "NTLM TlRMTVNTUAACAAAADgAOADgAAAAVgooCWJ7p4u8g4w4AAAAAAAAAAAA4ADgARgAAAAUBKAoAAAAPVABFAFMAVAACAA4AVABFAFMAVAABAA4AVABFAFMAVAAEAA4AdABlAHMAdAAuAGMAbwBtAAMAJAB0AGUAcwB0AC4AYwBvAG0AAAAAAAAABQAAAAAAAAAAAAAAAAAAAAAAAAAAADIwMjUtMDktMjkgMTE6MDA6MDBa",
                    "Content-Type": "application/mapi-http",
                    "X-ClientInfo": "365-Email-System/1.0",
                    "X-RequestId": request_id
                }
            )
        
        # Parse MAPI/HTTP request with improved error handling
        if len(body) > 0:
            try:
                mapi_request = MapiHttpRequest(body)
                parsed_request = mapi_request.parse()
            except Exception as parse_error:
                log_mapi("parse_error", {
                    "request_id": request_id,
                    "error": str(parse_error),
                    "body_len": len(body),
                    "hex_preview": body[:32].hex() if body else ""
                })
                
                outlook_diagnostics.log_error_with_context("mapi_parse_error", str(parse_error), {
                    "request_id": request_id,
                    "body_length": len(body),
                    "auth_type": auth_header.split(" ")[0] if " " in auth_header else auth_header[:10] if auth_header else "none"
                })
                
                # For Connect requests, try a simplified approach
                if len(body) >= 4:
                    # Assume it's a Connect request and build a simple response
                    parsed_request = {"type": "connect", "simplified": True}
                else:
                    raise parse_error
        else:
            # Empty body with Basic auth - Outlook often sends this as a test request
            if auth_header and auth_header.startswith("Basic"):
                log_mapi("empty_basic_request", {
                    "request_id": request_id,
                    "message": "Empty Basic auth request - treating as Connect test"
                })
                # Treat as a simplified Connect request
                parsed_request = {"type": "connect", "simplified": True, "test_request": True}
            else:
                # Empty body without any valid auth - this is an error
                log_outlook_connection_issue("invalid_empty_request", "Received empty MAPI request without valid auth", {
                    "request_id": request_id,
                    "auth_header": auth_header[:50] if auth_header else "none"
                })
                raise HTTPException(status_code=400, detail="Invalid MAPI request")
        
        logger.info(f"MAPI EMSMDB request: {parsed_request.get('type')}")
        
        # Build response based on request type
        response_builder = MapiHttpResponse()
        
        if parsed_request['type'] == 'connect':
            # Handle Connect request
            user_dn = parsed_request.get('user_dn', '')
            
            # Extract email from DN or use default
            user_email = "yonatan@shtrum.com"  # TODO: Extract from DN or authenticate
            
            # For simplified requests, use a default DN
            if parsed_request.get('simplified'):
                user_dn = f"/o=First Organization/ou=Exchange Administrative Group/cn=Recipients/cn={user_email.split('@')[0]}"
            
            # Create session
            session_cookie = session_manager.create_session(user_dn, user_email)
            
            # Build Connect response
            response_data = response_builder.build_connect_response(session_cookie)
            
            headers = {
                "Content-Type": "application/mapi-http",
                "X-RequestType": "Connect",
                "X-ClientInfo": "365-Email-System/1.0",
                "X-RequestId": request_id,
                "Cache-Control": "private",
                "X-SessionCookie": session_cookie,
                "X-ServerApplication": "365-Email-System/1.0",
                "X-ResponseCode": "0"
            }
            
            log_mapi("connect_success", {"session": session_cookie, "user_dn": user_dn})
            
        elif parsed_request['type'] == 'execute':
            # Handle Execute request
            session_cookie = parsed_request.get('session_cookie', '')
            rpc_data = parsed_request.get('rpc_data', b'')
            
            # Validate session
            session = session_manager.get_session(session_cookie)
            if not session:
                logger.warning(f"Invalid session cookie: {session_cookie}")
                return Response(
                    content=response_builder.build_error_response(0x80040111),
                    media_type="application/mapi-http",
                    status_code=401
                )
            
            # Update session activity
            session_manager.update_activity(session_cookie)
            
            # Process RPC data
            processor = get_rpc_processor()
            rpc_response = processor.process_rpc(session_cookie, rpc_data)
            
            # Build Execute response
            response_data = response_builder.build_execute_response(rpc_response)
            
            headers = {
                "Content-Type": "application/mapi-http",
                "X-RequestType": "Execute",
                "X-ClientInfo": "365-Email-System/1.0",
                "X-RequestId": str(uuid.uuid4()),
                "Cache-Control": "private",
                "X-SessionCookie": session_cookie
            }
            
            log_mapi("execute", {"session": session_cookie, "rpc_len": len(rpc_data)})
            
        elif parsed_request['type'] == 'disconnect':
            # Handle Disconnect request
            session_cookie = parsed_request.get('session_cookie', '')
            
            # Remove session
            if session_cookie in session_manager.sessions:
                del session_manager.sessions[session_cookie]
            
            # Build Disconnect response
            response_data = response_builder.build_disconnect_response()
            
            headers = {
                "Content-Type": "application/mapi-http",
                "X-RequestType": "Disconnect",
                "X-ClientInfo": "365-Email-System/1.0",
                "X-RequestId": str(uuid.uuid4()),
                "Cache-Control": "private"
            }
            
            log_mapi("disconnect", {"session": session_cookie})
            
        else:
            # Unknown request type
            logger.error(f"Unknown MAPI request type: {parsed_request.get('type')}")
            response_data = response_builder.build_error_response(0x80040111)
            headers = {
                "Content-Type": "application/mapi-http",
                "X-ClientInfo": "365-Email-System/1.0",
                "Cache-Control": "private"
            }
        
        return Response(content=response_data, media_type="application/mapi-http", headers=headers)
        
    except Exception as e:
        logger.error(f"Error processing MAPI EMSMDB request: {e}")
        log_mapi("error", {"error": str(e), "ua": ua})
        
        # Return error response
        response_builder = MapiHttpResponse()
        error_response = response_builder.build_error_response(0x80040111)
        
        return Response(
            content=error_response,
            media_type="application/mapi-http",
            status_code=500,
            headers={"X-ClientInfo": "365-Email-System/1.0"}
        )

@router.post("/nspi")
async def mapi_nspi(request: Request):
    """MAPI/HTTP NSPI endpoint - handles address book operations"""
    body = await request.body()
    ua = request.headers.get("User-Agent", "")
    content_type = request.headers.get("Content-Type", "")
    
    log_mapi("nspi", {
        "len": len(body), 
        "ua": ua, 
        "content_type": content_type,
        "method": "POST"
    })
    
    try:
        # For now, NSPI is a simpler stub - just return success
        # Real implementation would handle address book queries
        
        headers = {
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Bind",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": str(uuid.uuid4()),
            "Cache-Control": "private"
        }
        
        # Minimal NSPI success response
        response_data = b'\x00\x00\x00\x00'  # Success status
        
        log_mapi("nspi_success", {"len": len(response_data)})
        
        return Response(content=response_data, media_type="application/mapi-http", headers=headers)
        
    except Exception as e:
        logger.error(f"Error processing MAPI NSPI request: {e}")
        log_mapi("nspi_error", {"error": str(e), "ua": ua})
        
        return Response(
            content=b'\x11\x01\x04\x80',  # Error status
            media_type="application/mapi-http",
            status_code=500,
            headers={"X-ClientInfo": "365-Email-System/1.0"}
        )

# Root-level MAPI endpoints (Outlook might try these paths)
@root_router.post("/mapi/emsmdb")
async def root_mapi_emsmdb(request: Request):
    """Root-level MAPI/HTTP EMSMDB endpoint"""
    return await mapi_emsmdb(request)

@root_router.post("/mapi/nspi")  
async def root_mapi_nspi(request: Request):
    """Root-level MAPI/HTTP NSPI endpoint"""
    return await mapi_nspi(request)


