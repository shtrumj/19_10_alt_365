import base64
import logging
import os
import struct
import time
import uuid
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import authenticate_user
from ..database import SessionLocal, User, get_db
from ..diagnostic_logger import (
    _write_json_line,
    log_mapi_request,
    log_outlook_connection_issue,
    log_outlook_health,
    outlook_diagnostics,
)
from ..mapi_protocol import (
    MapiHttpRequest,
    MapiHttpRequestType,
    MapiHttpResponse,
    MapiRpcProcessor,
    session_manager,
)
from ..mapi_store import message_store
from ..services.gal_service import GalService

try:
    import gssapi  # Kerberos (Negotiate) acceptor
except Exception:
    gssapi = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mapi", tags=["mapihttp"])

# Also create a router without prefix for root-level MAPI endpoints
root_router = APIRouter(tags=["mapihttp-root"])


def log_mapi(event: str, details: dict):
    _write_json_line("web/mapi/mapi.log", {"event": event, **(details or {})})


def authenticate_basic_auth(auth_header: str, db: Session) -> Optional[User]:
    """Authenticate user from Basic Authentication header"""
    if not auth_header or not auth_header.startswith("Basic "):
        return None

    try:
        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return authenticate_user(db, username, password)
    except Exception as e:
        log_mapi("basic_auth_error", {"error": str(e)})
        return None


def log_outlook_debug(request: Request, event: str, details: dict = None):
    """Enhanced logging for Outlook debugging"""
    debug_details = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "request_id": str(uuid.uuid4()),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
        "method": request.method,
        "path": request.url.path,
        "headers": dict(request.headers),
        "is_outlook": "outlook" in request.headers.get("user-agent", "").lower(),
        "is_microsoft_office": "microsoft office"
        in request.headers.get("user-agent", "").lower(),
        "content_type": request.headers.get("content-type", ""),
        "authorization": request.headers.get("authorization", ""),
        "content_length": request.headers.get("content-length", "0"),
    }

    if details:
        debug_details.update(details)

    # Log to both MAPI log and debug log
    _write_json_line("web/mapi/mapi.log", debug_details)
    _write_json_line("outlook_debug/communication.log", debug_details)


def _extract_auth_info(auth_header: Optional[str]) -> Tuple[str, Optional[str], bytes]:
    """Return normalized scheme, token string, and decoded bytes for NTLM detection."""
    if not auth_header:
        return "", None, b""

    scheme, _, token = auth_header.partition(" ")
    scheme_lower = scheme.lower()
    token = token.strip() if token else ""
    raw = b""
    if token:
        try:
            raw = base64.b64decode(token + "==")
        except Exception:
            raw = b""

    # When Outlook uses Negotiate but offers NTLM inside, treat it as NTLM
    if scheme_lower == "negotiate" and raw.startswith(b"NTLMSSP\x00"):
        return "ntlm", token or None, raw

    return scheme_lower, token or None, raw


# Initialize RPC processor
rpc_processor = None


def get_rpc_processor():
    global rpc_processor
    if rpc_processor is None:
        db = SessionLocal()
        rpc_processor = MapiRpcProcessor(db)
    return rpc_processor


def _to_utf16le(s: str) -> bytes:
    return s.encode("utf-16le")


def _filetime_now() -> bytes:
    # FILETIME = 100-nanosecond intervals since Jan 1, 1601 (UTC)
    EPOCH_DIFF = 11644473600  # seconds between 1601 and 1970
    ft = int((time.time() + EPOCH_DIFF) * 10_000_000)
    return struct.pack("<Q", ft)


def _build_ntlm_type2(hostname: str) -> str:
    """Build a NTLM Type 2 challenge token with common AV pairs.
    Not a full implementation; sufficient for client negotiation.
    """
    signature = b"NTLMSSP\x00"
    msg_type = struct.pack("<I", 2)

    # Parse host into parts
    dns_host = hostname
    if "." in hostname:
        dns_domain = hostname.split(".", 1)[1]
        nb_host = hostname.split(".", 1)[0].upper()
        nb_domain = dns_domain.split(".", 1)[0].upper()
    else:
        dns_domain = hostname
        nb_host = hostname.upper()
        nb_domain = hostname.upper()

    # Random server challenge
    challenge = os.urandom(8)

    # Flags: include Unicode, NTLM, AlwaysSign, TargetTypeServer, NTLM2KEY,
    # Target Info present, 128/56-bit, RequestTarget, NegotiateTarget, Version
    # Note: Removed OEM flag (0x00000002) as it can cause Outlook compatibility issues
    flags = (
        0x00000001  # UNICODE
        | 0x00000200  # SIGN
        | 0x00080000  # NTLM2 KEY
        | 0x00010000  # TargetTypeServer
        | 0x00020000  # NTLM
        | 0x00004000  # Target Info
        | 0x00000004  # Request Target
        | 0x00001000  # Negotiate Target
        | 0x02000000  # Negotiate Version
        | 0x20000000  # 128-bit
        | 0x80000000  # 56-bit
    )
    negotiate_flags = struct.pack("<I", flags & 0xFFFFFFFF)

    # Target name (NetBIOS host)
    target_name = _to_utf16le(nb_host)
    target_name_len = struct.pack("<H", len(target_name))
    target_name_sec = target_name_len + target_name_len  # maxlen same

    # AV Pairs
    def av_pair(av_id: int, val: bytes) -> bytes:
        return struct.pack("<H", av_id) + struct.pack("<H", len(val)) + val

    AV_EOL = struct.pack("<H", 0) + struct.pack("<H", 0)
    av_nb_computer = av_pair(0x0001, _to_utf16le(nb_host))
    av_nb_domain = av_pair(0x0002, _to_utf16le(nb_domain))
    av_dns_computer = av_pair(0x0003, _to_utf16le(dns_host))
    av_dns_domain = av_pair(0x0004, _to_utf16le(dns_domain))
    av_timestamp = av_pair(0x0007, _filetime_now())
    target_info = (
        av_nb_computer
        + av_nb_domain
        + av_dns_computer
        + av_dns_domain
        + av_timestamp
        + AV_EOL
    )

    # Offsets
    header_len = 48  # up to TargetInfo sec buffer
    target_name_offset = header_len
    target_info_offset = header_len + len(target_name)

    target_name_sec += struct.pack("<I", target_name_offset)
    target_info_sec = (
        struct.pack("<H", len(target_info))
        + struct.pack("<H", len(target_info))
        + struct.pack("<I", target_info_offset)
    )

    # Context (8 bytes)
    context = b"\x00" * 8

    # Version (Windows 10.0 build 19041 like)
    version = b"\x0a\x00\x00\x00\x00\x00\x00\x0f"

    payload = target_name + target_info

    type2 = (
        signature
        + msg_type
        + target_name_sec
        + negotiate_flags
        + challenge
        + context
        + target_info_sec
        + payload
        + version
    )
    return base64.b64encode(type2).decode("ascii")


@router.post("/emsmdb")
async def mapi_emsmdb(request: Request):
    """MAPI/HTTP EMSMDB endpoint - handles mailbox operations"""
    body = await request.body()
    ua = request.headers.get("User-Agent", "")
    content_type = request.headers.get("Content-Type", "")
    auth_header = request.headers.get("Authorization")
    auth_scheme, auth_token, auth_raw = _extract_auth_info(auth_header)

    # Start enhanced diagnostic logging
    request_id = str(uuid.uuid4())

    # Enhanced logging for Outlook debugging
    log_mapi(
        "emsmdb",
        {
            "request_id": request_id,
            "len": len(body),
            "ua": ua,
            "content_type": content_type,
            "method": "POST",
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else "unknown",
            "has_auth": bool(auth_header),
            "auth_type": auth_scheme or "none",
        },
    )

    # Log this as an Outlook phase
    outlook_diagnostics.log_outlook_phase(
        "mapi_request_received",
        {
            "request_id": request_id,
            "content_length": len(body),
            "has_authentication": bool(auth_header),
            "user_agent": ua,
        },
    )

    try:
        # Enhanced authentication handling
        if auth_header:
            log_mapi(
                "auth_received",
                {
                    "request_id": request_id,
                    "auth_type": auth_scheme or "unknown",
                    "has_credentials": len(auth_header or "") > 10,
                },
            )

            # Log authentication attempt
            outlook_diagnostics.log_authentication_flow(
                auth_scheme or "unknown",
                "credentials_received",
                True,
                {"request_id": request_id, "user_agent": ua},
            )

            # Decode Basic auth for logging (without exposing password)
            if auth_scheme == "basic" and auth_token:
                try:
                    decoded = base64.b64decode(auth_token).decode("utf-8")
                    username = decoded.split(":")[0] if ":" in decoded else "unknown"
                    log_mapi(
                        "basic_auth_user",
                        {"request_id": request_id, "username": username},
                    )
                except:
                    pass

        elif len(body) == 0:
            # Empty request without auth - send NTLM challenge
            log_mapi(
                "auth_challenge",
                {
                    "request_id": request_id,
                    "reason": "no_auth_header",
                    "challenge_type": "NTLM",
                },
            )

            outlook_diagnostics.log_authentication_flow(
                "NTLM",
                "challenge_sent",
                True,
                {"request_id": request_id, "reason": "no_auth_header"},
            )

            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="365-Email-System"',
                    "Content-Type": "application/mapi-http",
                    "X-ClientInfo": "365-Email-System/1.0",
                    "X-RequestId": request_id,
                    "Persistent-Auth": "true",
                    "X-ServerApplication": "365-Email-System/1.0",
                    "Connection": "close",
                    "Cache-Control": "private",
                },
            )

        # Log the raw request for debugging
        log_mapi(
            "raw_request",
            {
                "length": len(body),
                "hex_preview": body[:32].hex() if len(body) > 0 else "",
                "auth_type": auth_scheme or "none",
            },
        )

        # For now, accept any request with body without full authentication validation
        # Real implementation would validate NTLM/Kerberos tokens

        # Handle NTLM authentication flow properly
        # Handle Kerberos/Negotiate (GSSAPI) if presented
        if auth_scheme == "negotiate":
            token_b64 = auth_token or ""
            try:
                in_token = base64.b64decode(token_b64)
                if gssapi is not None:
                    srv_creds = gssapi.Credentials(usage="accept")
                    ctx = gssapi.SecurityContext(creds=srv_creds)
                    out_token = ctx.step(in_token)
                    # If context not complete yet, send 401 with Negotiate out token
                    if out_token is not None and not ctx.complete:
                        log_mapi("gss_negotiate_continue", {"request_id": request_id})
                        return Response(
                            status_code=401,
                            headers={
                                "WWW-Authenticate": f"Negotiate {base64.b64encode(out_token).decode('ascii')}",
                                "Content-Type": "application/mapi-http",
                                "X-ClientInfo": "365-Email-System/1.0",
                                "X-RequestId": request_id,
                                "X-RequestType": "Connect",
                                "Cache-Control": "private",
                                "Connection": "close",
                            },
                        )
                    # If complete, accept and return 200 Connect
                    if ctx.complete:
                        log_mapi("gss_authenticated", {"request_id": request_id})
                        return Response(
                            status_code=200,
                            headers={
                                "Content-Type": "application/mapi-http",
                                "X-RequestType": "Connect",
                                "X-ClientInfo": "365-Email-System/1.0",
                                "X-RequestId": request_id,
                                "X-ResponseCode": "0",
                                "Cache-Control": "private",
                            },
                        )
                # If gssapi not available or failed, fallthrough to NTLM path
            except Exception as gss_err:
                log_mapi("gss_error", {"request_id": request_id, "error": str(gss_err)})
            else:
                if gssapi is None:
                    log_mapi("gss_not_available", {"request_id": request_id})
            # If we've reached here, force NTLM fallback
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": "NTLM",
                    "Content-Type": "application/mapi-http",
                    "Persistent-Auth": "true",
                    "Connection": "close",
                },
            )

        if auth_scheme == "ntlm" and len(body) == 0:
            # Distinguish NTLM Type1 (negotiate) vs Type3 (authenticate) by token length
            token = auth_token or ""
            if token and len(token) <= 64:
                # NTLM Type 1 negotiate received -> send Type 2 challenge
                log_mapi(
                    "ntlm_negotiation",
                    {
                        "request_id": request_id,
                        "stage": "type1_received",
                        "body_length": len(body),
                    },
                )

                outlook_diagnostics.log_authentication_flow(
                    "NTLM",
                    "type1_received",
                    True,
                    {"request_id": request_id, "next_step": "send_type2_challenge"},
                )

                # Generate Type 2 challenge dynamically based on host
                host = request.headers.get("Host", "server")
                ntlm_type2 = _build_ntlm_type2(host.split(":")[0])
                log_mapi(
                    "ntlm_type2_sent",
                    {
                        "request_id": request_id,
                        "len": len(ntlm_type2),
                        "head": ntlm_type2[:60],
                    },
                )

                return Response(
                    status_code=401,
                    headers={
                        "WWW-Authenticate": f"NTLM {ntlm_type2}",
                        "Content-Type": "application/mapi-http",
                        "X-ClientInfo": "365-Email-System/1.0",
                        "X-RequestId": request_id,
                        "X-RequestType": "Connect",
                        "Cache-Control": "private",
                        "Connection": "close",
                        "Persistent-Auth": "true",
                        "X-ServerApplication": "365-Email-System/1.0",
                    },
                )
            else:
                # Detect NTLM Type 3 by message type field
                try:
                    raw = auth_raw or base64.b64decode(token + "==")  # tolerate padding
                    is_ntlm = raw.startswith(b"NTLMSSP\x00")
                    msg_type = (
                        struct.unpack("<I", raw[8:12])[0] if len(raw) >= 12 else 0
                    )
                except Exception:
                    is_ntlm = False
                    msg_type = 0
                if is_ntlm and msg_type == 3:
                    # NTLM Type 3 authenticate received -> accept and return Connect success
                    log_mapi(
                        "ntlm_authenticated",
                        {
                            "request_id": request_id,
                            "stage": "type3_received",
                            "token_len": len(token),
                        },
                    )
                    outlook_diagnostics.log_authentication_flow(
                        "NTLM", "type3_received", True, {"request_id": request_id}
                    )
                return Response(
                    status_code=200,
                    headers={
                        "Content-Type": "application/mapi-http",
                        "X-RequestType": "Connect",
                        "X-ClientInfo": "365-Email-System/1.0",
                        "X-RequestId": request_id,
                        "X-ResponseCode": "0",
                        "Cache-Control": "private",
                        "Persistent-Auth": "true",
                        "X-ServerApplication": "365-Email-System/1.0",
                        "X-ServerVersion": "15.01.2507.000",
                        "X-ClientApplication": "SkyShift-Exchange/1.0",
                        "Content-Length": "0",
                    },
                )

        # Parse MAPI/HTTP request with improved error handling
        if len(body) > 0:
            try:
                mapi_request = MapiHttpRequest(body)
                parsed_request = mapi_request.parse()
            except Exception as parse_error:
                log_mapi(
                    "parse_error",
                    {
                        "request_id": request_id,
                        "error": str(parse_error),
                        "body_len": len(body),
                        "hex_preview": body[:32].hex() if body else "",
                    },
                )

                outlook_diagnostics.log_error_with_context(
                    "mapi_parse_error",
                    str(parse_error),
                    {
                        "request_id": request_id,
                        "body_length": len(body),
                        "auth_type": auth_scheme or "none",
                    },
                )

                # For Connect requests, try a simplified approach
                if len(body) >= 4:
                    # Assume it's a Connect request and build a simple response
                    parsed_request = {"type": "connect", "simplified": True}
                else:
                    raise parse_error
        else:
            # Empty body with Basic auth - authenticate the user
            if auth_header and auth_header.startswith("Basic"):
                # Authenticate the user with Basic auth
                db = SessionLocal()
                try:
                    user = authenticate_basic_auth(auth_header, db)
                    if user:
                        log_mapi(
                            "basic_auth_success",
                            {
                                "request_id": request_id,
                                "username": user.username,
                                "message": "Basic auth successful - proceeding with MAPI",
                            },
                        )
                        outlook_diagnostics.log_authentication_flow(
                            "Basic",
                            "authentication_successful",
                            True,
                            {"request_id": request_id, "username": user.username},
                        )

                        # Return a successful MAPI response
                        return Response(
                            status_code=200,
                            headers={
                                "Content-Type": "application/mapi-http",
                                "X-ClientInfo": "365-Email-System/1.0",
                                "X-RequestId": request_id,
                                "X-RequestType": "Connect",
                                "Cache-Control": "private",
                                "Connection": "close",
                                "Persistent-Auth": "true",
                                "X-ServerApplication": "365-Email-System/1.0",
                                "X-ServerVersion": "15.01.2507.000",
                                "X-ClientApplication": "SkyShift-Exchange/1.0",
                            },
                            content=b"\x00\x00\x00\x00",  # Empty MAPI response
                        )
                    else:
                        log_mapi(
                            "basic_auth_failed",
                            {
                                "request_id": request_id,
                                "message": "Basic auth failed - invalid credentials",
                            },
                        )
                        outlook_diagnostics.log_authentication_flow(
                            "Basic",
                            "authentication_failed",
                            False,
                            {"request_id": request_id},
                        )
                        return Response(
                            status_code=401,
                            headers={
                                "WWW-Authenticate": "Basic",
                                "Content-Type": "application/mapi-http",
                                "X-RequestId": request_id,
                            },
                        )
                finally:
                    db.close()
            else:
                # Empty body without any valid auth - this is an error
                log_outlook_connection_issue(
                    "invalid_empty_request",
                    "Received empty MAPI request without valid auth",
                    {
                        "request_id": request_id,
                        "auth_header": auth_header[:50] if auth_header else "none",
                    },
                )
                raise HTTPException(status_code=400, detail="Invalid MAPI request")

        logger.info(f"MAPI EMSMDB request: {parsed_request.get('type')}")

        # Build response based on request type
        response_builder = MapiHttpResponse()

        if parsed_request["type"] == "connect":
            # Handle Connect request
            user_dn = parsed_request.get("user_dn", "")

            # Extract email from DN or use default
            user_email = "yonatan@shtrum.com"  # TODO: Extract from DN or authenticate

            # For simplified requests, use a default DN
            if parsed_request.get("simplified"):
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
                "X-ResponseCode": "0",
                "X-ServerVersion": "15.01.2507.000",
                "X-ClientApplication": "SkyShift-Exchange/1.0",
            }

            log_mapi("connect_success", {"session": session_cookie, "user_dn": user_dn})

        elif parsed_request["type"] == "execute":
            # Handle Execute request
            session_cookie = parsed_request.get("session_cookie", "")
            rpc_data = parsed_request.get("rpc_data", b"")

            # Validate session
            session = session_manager.get_session(session_cookie)
            if not session:
                logger.warning(f"Invalid session cookie: {session_cookie}")
                return Response(
                    content=response_builder.build_error_response(0x80040111),
                    media_type="application/mapi-http",
                    status_code=401,
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
                "X-SessionCookie": session_cookie,
            }

            log_mapi("execute", {"session": session_cookie, "rpc_len": len(rpc_data)})

        elif parsed_request["type"] == "disconnect":
            # Handle Disconnect request
            session_cookie = parsed_request.get("session_cookie", "")

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
                "Cache-Control": "private",
            }

            log_mapi("disconnect", {"session": session_cookie})

        else:
            # Unknown request type
            logger.error(f"Unknown MAPI request type: {parsed_request.get('type')}")
            response_data = response_builder.build_error_response(0x80040111)
            headers = {
                "Content-Type": "application/mapi-http",
                "X-ClientInfo": "365-Email-System/1.0",
                "Cache-Control": "private",
            }

        return Response(
            content=response_data, media_type="application/mapi-http", headers=headers
        )

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
            headers={"X-ClientInfo": "365-Email-System/1.0"},
        )


@router.get("/nspi")
@router.post("/nspi")
async def mapi_nspi(request: Request, db: Session = Depends(get_db)):
    """MAPI/HTTP NSPI endpoint - handles address book operations"""
    body = await request.body()
    ua = request.headers.get("User-Agent", "")
    content_type = request.headers.get("Content-Type", "")
    request_id = str(uuid.uuid4())

    log_mapi(
        "nspi",
        {
            "request_id": request_id,
            "len": len(body),
            "ua": ua,
            "content_type": content_type,
            "method": "POST",
        },
    )

    try:
        # Enhanced NSPI implementation for GAL operations
        if len(body) >= 8:
            # Parse NSPI request (simplified)
            operation = struct.unpack("<I", body[0:4])[0]

            if operation == 0x01:  # NspiGetMatches (GAL search)
                log_mapi("nspi_get_matches", {"request_id": request_id})

                gal_service = GalService(db)
                search_term = ""
                if len(body) > 8:
                    candidate = body[8:]
                    try:
                        search_term = (
                            candidate.decode("utf-16-le", errors="ignore")
                            .strip("\x00")
                            .strip()
                        )
                    except Exception:
                        search_term = (
                            candidate.decode("utf-8", errors="ignore")
                            .strip("\x00")
                            .strip()
                        )
                entries = gal_service.search(search_term or None, limit=100)

                # Build NSPI response with user data
                response_data = struct.pack("<I", 0)  # Success status
                response_data += struct.pack("<I", len(entries))  # Entry count

                def _pack_string(value: str, max_len: int = 255) -> bytes:
                    encoded = (value or "").encode("utf-8")[:max_len]
                    return struct.pack("<H", len(encoded)) + encoded

                for entry in entries:
                    response_data += _pack_string(entry.display_name or entry.email)
                    response_data += _pack_string(entry.email)
                    response_data += _pack_string(entry.company or "")
                    response_data += _pack_string(entry.department or "")

                log_mapi(
                    "nspi_response",
                    {
                        "request_id": request_id,
                        "user_count": len(entries),
                        "operation": "GetMatches",
                        "query": search_term,
                    },
                )

            else:
                # Default NSPI response for other operations
                response_data = struct.pack("<I", 0)  # Success status
        else:
            # Empty or short request - return basic success
            response_data = struct.pack("<I", 0)  # Success status

        headers = {
            "Content-Type": "application/mapi-http",
            "X-RequestType": "AddressBook",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
        }

        log_mapi("nspi_success", {"request_id": request_id, "len": len(response_data)})

        return Response(
            content=response_data, media_type="application/mapi-http", headers=headers
        )

    except Exception as e:
        logger.error(f"Error processing MAPI NSPI request: {e}")
        log_mapi("nspi_error", {"error": str(e), "ua": ua})

        return Response(
            content=b"\x11\x01\x04\x80",  # Error status
            media_type="application/mapi-http",
            status_code=500,
            headers={"X-ClientInfo": "365-Email-System/1.0"},
        )


@router.get("/emsmdb")
@router.head("/emsmdb")
async def mapi_emsmdb_get(request: Request):
    """Respond to Outlook probe with NTLM challenge on GET."""
    request_id = str(uuid.uuid4())
    ua = request.headers.get("User-Agent", "")
    log_mapi(
        "emsmdb_get",
        {
            "request_id": request_id,
            "ua": ua,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )

    # Enhanced Outlook debugging
    log_outlook_debug(
        request,
        "emsmdb_get_request",
        {
            "request_id": request_id,
            "stage": "initial_get",
            "outlook_detected": "outlook" in ua.lower(),
        },
    )
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="365-Email-System"',
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
            "Connection": "close",
            "Persistent-Auth": "true",
            "X-ServerApplication": "365-Email-System/1.0",
        },
    )


@router.head("/emsmdb")
async def mapi_emsmdb_head(request: Request):
    request_id = str(uuid.uuid4())
    log_mapi(
        "emsmdb_head",
        {
            "request_id": request_id,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="365-Email-System"',
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
            "Connection": "close",
            "Persistent-Auth": "true",
            "X-ServerApplication": "365-Email-System/1.0",
        },
    )


@router.options("/emsmdb")
async def mapi_emsmdb_options(request: Request):
    request_id = str(uuid.uuid4())
    log_mapi(
        "emsmdb_options",
        {
            "request_id": request_id,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return Response(
        status_code=200,
        headers={
            "Allow": "GET,POST,HEAD,OPTIONS",
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
        },
    )


@root_router.get("/mapi/emsmdb")
async def mapi_emsmdb_get_root(request: Request):
    """Root-level GET probe compatibility for Outlook."""
    request_id = str(uuid.uuid4())
    ua = request.headers.get("User-Agent", "")
    log_mapi(
        "emsmdb_get_root",
        {
            "request_id": request_id,
            "ua": ua,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="365-Email-System"',
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
            "Connection": "close",
            "Persistent-Auth": "true",
            "X-ServerApplication": "365-Email-System/1.0",
        },
    )


@root_router.head("/mapi/emsmdb")
async def mapi_emsmdb_head_root(request: Request):
    request_id = str(uuid.uuid4())
    log_mapi(
        "emsmdb_head_root",
        {
            "request_id": request_id,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="365-Email-System"',
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
            "Connection": "close",
            "Persistent-Auth": "true",
            "X-ServerApplication": "365-Email-System/1.0",
        },
    )


@root_router.options("/mapi/emsmdb")
async def mapi_emsmdb_options_root(request: Request):
    request_id = str(uuid.uuid4())
    log_mapi(
        "emsmdb_options_root",
        {
            "request_id": request_id,
            "client_ip": request.client.host if request.client else "unknown",
        },
    )
    return Response(
        status_code=200,
        headers={
            "Allow": "GET,POST,HEAD,OPTIONS",
            "Content-Type": "application/mapi-http",
            "X-RequestType": "Connect",
            "X-ClientInfo": "365-Email-System/1.0",
            "X-RequestId": request_id,
            "Cache-Control": "private",
        },
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
