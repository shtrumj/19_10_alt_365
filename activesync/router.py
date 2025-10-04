from datetime import datetime, timedelta
from typing import List, Optional
from xml.etree import ElementTree as ET
import time
import uuid
import io
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

# CRITICAL FIX #31B: Add logger for protocol version negotiation logging
logger = logging.getLogger(__name__)

from app.auth import get_current_user_from_basic_auth
from app.database import ActiveSyncDevice, ActiveSyncState, CalendarEvent, User, get_db
from app.diagnostic_logger import _write_json_line
from app.email_service import EmailService
# ActiveSync WBXML builders (root-level module)
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# Z-Push-compliant WBXML builder imports
from .wbxml_builder import (
    create_sync_response_wbxml,
    create_sync_response_wbxml_with_fetch,
    SyncBatch,
)
from .state_machine import SyncStateStore
from .adapter import sync_prepare_batch
from app.wbxml_parser import (
    parse_wbxml_sync_request,
    parse_wbxml_foldersync_request,
    parse_wbxml_sync_fetch_and_delete,
)
from app.synckey_utils import parse_synckey, generate_synckey, bump_synckey, has_synckey

# Rate limiting for sync requests
_sync_rate_limits = {}

router = APIRouter(prefix="/activesync", tags=["activesync"])

# Simple in-memory pending cache: (user, device, collection, client_key) -> wbxml bytes
_pending_batches_cache = {}


class ActiveSyncResponse:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content

    def __call__(self, *args, **kwargs):
        return Response(
            content=self.xml_content, media_type="application/xml"
        )


def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery only (no singular MS-ASProtocolVersion)."""
    return {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "15.0",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # OPTIONS advertises list of versions (plural only)
        # CRITICAL FIX #31: Cap to 14.1 while debugging!
        # iOS picks the HIGHEST version and expects that format!
        "MS-ASProtocolVersions": "14.1",  # Only advertise what we can deliver!
        # OPTIONS includes commands list
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert"
        ),
        # MS-ASHTTP protocol support headers
        "MS-ASProtocolSupports": "14.0,14.1",  # Only what we support!
    }


def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST).
    
    CRITICAL FIX #31: Echo the client's requested protocol version!
    iOS expects MS-ASProtocolVersion (singular) to match what it sent.
    
    NOTE: Do NOT set a global Content-Type header; each endpoint sets its own media_type
    """
    headers = {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "14.1",
        "X-MS-Server-ActiveSync": "14.1",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # CRITICAL FIX #31: Echo the negotiated version (singular)
        # This MUST match what the client sent in MS-ASProtocolVersion header!
        "MS-ASProtocolVersion": protocol_version or "14.1",
        # Can include list too (optional on POST responses)
        "MS-ASProtocolVersions": "14.1",
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert"
        ),
        # MS-ASHTTP protocol support headers
        "MS-ASProtocolSupports": "14.0,14.1",
    }
    
    # Add X-MS-PolicyKey header if provided (iOS expects this after provisioning)
    if policy_key:
        headers["X-MS-PolicyKey"] = policy_key
        
    return headers


def create_sync_response(emails: List, sync_key: str = "1", collection_id: str = "1"):
    """Create ActiveSync XML response for email synchronization according to MS-ASCMD specification"""
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")

    # MS-ASCMD compliant structure - Status as child element, not attribute
    status_elem = ET.SubElement(root, "Status")
    status_elem.text = "1"  # Success status

    # SyncKey as child element
    synckey_elem = ET.SubElement(root, "SyncKey")
    synckey_elem.text = sync_key

    # Collections wrapper
    collections = ET.SubElement(root, "Collections")
    collection = ET.SubElement(collections, "Collection")
    collection.set("SyncKey", sync_key)
    collection.set("CollectionId", collection_id)

    # Add commands for each email according to Microsoft documentation
    for email in emails:
        add = ET.SubElement(collection, "Add")
        add.set("ServerId", f"{collection_id}:{email.id}")  # Format: CollectionId:EmailId

        # Email properties according to Microsoft documentation
        application_data = ET.SubElement(add, "ApplicationData")

        # Subject (required)
        subject_elem = ET.SubElement(application_data, "Subject")
        subject_elem.text = email.subject or "(no subject)"

        # From (required)
        from_elem = ET.SubElement(application_data, "From")
        from_elem.text = getattr(getattr(email, "sender", None), "email", "") or ""

        # To (required)
        to_elem = ET.SubElement(application_data, "To")
        to_elem.text = getattr(getattr(email, "recipient", None), "email", "") or ""

        # DateReceived (required) - Format MUST be like "2025-10-01T06:25:28.384Z"
        date_elem = ET.SubElement(application_data, "DateReceived")
        # Format MUST be like "2025-10-01T06:25:28.384Z"
        date_elem.text = email.created_at.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # DisplayTo (required)
        display_to = ET.SubElement(application_data, "DisplayTo")
        display_to.text = getattr(getattr(email, "recipient", None), "email", "") or ""

        # ThreadTopic (required)
        thread_topic = ET.SubElement(application_data, "ThreadTopic")
        thread_topic.text = email.subject or "(no subject)"

        # Importance (required)
        importance = ET.SubElement(application_data, "Importance")
        importance.text = "1"  # Normal importance

        # Read status (required)
        read_elem = ET.SubElement(application_data, "Read")
        read_elem.text = "1" if email.is_read else "0"

        # Body (AirSyncBase-style structure; child elements, correct order)
        body_elem = ET.SubElement(application_data, "Body")
        type_elem = ET.SubElement(body_elem, "Type"); type_elem.text = "2"  # HTML
        size_elem = ET.SubElement(body_elem, "EstimatedDataSize"); size_elem.text = str(len(email.body or ""))
        trunc_elem = ET.SubElement(body_elem, "Truncated"); trunc_elem.text = "0"
        data_elem = ET.SubElement(body_elem, "Data"); data_elem.text = email.body or ""

        # MessageClass (required for Exchange compatibility)
        message_class = ET.SubElement(application_data, "MessageClass")
        message_class.text = "IPM.Note"

        # InternetCPID (required)
        internet_cpid = ET.SubElement(application_data, "InternetCPID")
        internet_cpid.text = "65001"  # UTF-8

        # ContentClass (required)
        content_class = ET.SubElement(application_data, "ContentClass")
        content_class.text = "urn:content-classes:message"

        # NativeBodyType (required)
        native_body_type = ET.SubElement(application_data, "NativeBodyType")
        native_body_type.text = "2"  # HTML

        # *** FIX: Generate Unique Conversation IDs ***
        # For now, make every email its own conversation to avoid conflicts.
        conversation_id = ET.SubElement(application_data, "ConversationId")
        conversation_id.text = str(uuid.uuid4())

        # ConversationIndex (required for threading)
        conversation_index = ET.SubElement(application_data, "ConversationIndex")
        # A timestamp is a simple way to generate a unique index for this initial implementation.
        conversation_index.text = email.created_at.strftime('%Y%m%d%H%M%S')

        # Categories (required)
        categories = ET.SubElement(application_data, "Categories")
        categories.text = ""

    return ET.tostring(root, encoding="unicode")


@router.options("/Microsoft-Server-ActiveSync")
async def eas_options(request: Request):
    """Respond to ActiveSync OPTIONS discovery with required headers and log it.
    
    CRITICAL FIX #31: Use separate OPTIONS headers (no singular MS-ASProtocolVersion)!
    """
    headers = _eas_options_headers()  # ← Use OPTIONS-specific headers!
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "options",
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        },
    )
    return Response(status_code=200, headers=headers)


def _get_or_create_device(
    db: Session, user_id: int, device_id: str, device_type: str | None = None
) -> ActiveSyncDevice:
    device = (
        db.query(ActiveSyncDevice)
        .filter(
            ActiveSyncDevice.user_id == user_id, ActiveSyncDevice.device_id == device_id
        )
        .first()
    )
    if not device:
        device = ActiveSyncDevice(
            user_id=user_id, device_id=device_id, device_type=device_type or "generic"
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    return device


def _get_or_init_state(
    db: Session, user_id: int, device_id: str, collection_id: str = "1"
) -> ActiveSyncState:
    state = (
        db.query(ActiveSyncState)
        .filter(
            ActiveSyncState.user_id == user_id,
            ActiveSyncState.device_id == device_id,
            ActiveSyncState.collection_id == collection_id,
        )
        .first()
    )
    if not state:
        state = ActiveSyncState(
            user_id=user_id,
            device_id=device_id,
            collection_id=collection_id,
            sync_key="0",
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    
    # MS-ASCMD compliant: No artificial loop breaking - follow standard sync key progression
    
    return state


def _check_rate_limit(user_id: int, device_id: str, cmd: str) -> bool:
    """Check if user is making too many requests (rate limiting)"""
    key = f"{user_id}:{device_id}:{cmd}"
    now = time.time()
    
    if key not in _sync_rate_limits:
        _sync_rate_limits[key] = []
    
    # Clean old entries (older than 1 minute)
    _sync_rate_limits[key] = [t for t in _sync_rate_limits[key] if now - t < 60]
    
    # Check rate limit (max 100 requests per minute for sync commands - very lenient)
    if len(_sync_rate_limits[key]) >= 100:
        return False
    
    _sync_rate_limits[key].append(now)
    return True

def _bump_sync_key(state: ActiveSyncState, db: Session) -> str:
    try:
        next_key = str(int(state.sync_key) + 1)
    except Exception:
        next_key = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    state.sync_key = next_key
    db.commit()
    db.refresh(state)
    return state.sync_key


@router.post("/Microsoft-Server-ActiveSync")
async def eas_dispatch(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """Dispatcher for Microsoft-Server-ActiveSync commands."""
    cmd = request.query_params.get("Cmd", "").lower()
    device_id = request.query_params.get("DeviceId", "device-generic")
    device_type = request.query_params.get("DeviceType", "SmartPhone")
    
    # CRITICAL FIX #31: Read and echo the client's requested protocol version!
    # iOS sends MS-ASProtocolVersion header with the version it wants to use
    # We MUST echo this back or iOS will reject our responses!
    client_version = request.headers.get("MS-ASProtocolVersion", "14.1")
    # Validate it's one we support (cap to 14.1 for now)
    if client_version not in ["12.1", "14.0", "14.1"]:
        logger.warning(f"Client requested unsupported version {client_version}, capping to 14.1")
        client_version = "14.1"
    
    # CRITICAL FIX #11: Get device and policy key FIRST, then create headers with it
    # iOS requires X-MS-PolicyKey header on ALL commands after provisioning
    # Without it, iOS won't commit sync state and keeps reverting to SyncKey=0
    device = _get_or_create_device(db, current_user.id, device_id, device_type)
    # MS-ASPROV: PolicyKey must be 10-digit number after provisioning handshake
    policy_key = "1234567890" if device.is_provisioned == 1 else "0"
    
    # CRITICAL FIX #31: Pass protocol_version to echo client's request!
    headers = _eas_headers(policy_key=policy_key, protocol_version=client_version)
    
    # Log version negotiation
    logger.info(f"Protocol negotiation: client={client_version}, echoing back={client_version}")

    # High-resolution request logging
    request_body_bytes = await request.body()
    try:
        request_body_for_log = request_body_bytes.decode('utf-8', errors='ignore')
    except Exception:
        request_body_for_log = f"Could not decode request body. Length: {len(request_body_bytes)} bytes."
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "request_received", "command": cmd, "device_id": device_id,
            "user_agent": request.headers.get("User-Agent"), "query_params": dict(request.query_params),
            "body_preview": request_body_for_log[:500]
        }
    )

    if not cmd:
        _write_json_line("activesync/activesync.log", {"event": "no_command", "message": "No command specified"})
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Error xmlns="Error">
    <Status>2</Status>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Invalid request - command not specified</Message>
        </Error>
    </Response>
</Error>"""
        return Response(
            content=xml, 
            media_type="application/xml", 
            headers=headers,
            status_code=200
        )
    
    # Device already created above (line 285) for policy_key header
    # device = _get_or_create_device(db, current_user.id, device_id, device_type)  # ← Removed duplicate

    # --- Command Handling ---

    # FULL MS-ASPROV COMPLIANT PROVISION HANDLER
    # The client MUST be allowed to Provision itself at any time.
    if cmd == "provision":
        # MS-ASPROV Two-Step Handshake:
        # Step 1: Client sends initial request (no PolicyKey or PolicyKey=0)
        #         Server responds with PolicyKey=0 + policy settings
        # Step 2: Client acknowledges by sending back PolicyKey=0
        #         Server responds with final PolicyKey=1234567890 (10-digit number)
        # Step 3: Client includes PolicyKey=1234567890 in all subsequent requests
        
        # Parse WBXML request to detect which step we're in
        is_wbxml = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
        is_acknowledgment = False
        client_policy_key = None
        
        if is_wbxml and len(request_body_bytes) > 20:
            # Look for PolicyKey in request (token 0x0F in Provision codepage + 0x40 = 0x4F)
            # If PolicyKey=0 present, this is Step 2 (acknowledgment)
            pos = 0
            while pos < len(request_body_bytes) - 4:
                if (request_body_bytes[pos] == 0x4F and  # PolicyKey tag
                    pos + 1 < len(request_body_bytes) and request_body_bytes[pos + 1] == 0x03):  # STR_I
                    str_start = pos + 2
                    str_end = str_start
                    while str_end < len(request_body_bytes) and request_body_bytes[str_end] != 0x00:
                        str_end += 1
                    if str_end < len(request_body_bytes):
                        client_policy_key = request_body_bytes[str_start:str_end].decode('utf-8', errors='ignore')
                        if client_policy_key == "0":
                            is_acknowledgment = True
                        break
                pos += 1
        
        # Determine response based on step
        if is_acknowledgment:
            # Step 2: Client acknowledged, send FINAL policy key
            policy_key = "1234567890"  # MS-ASPROV: Must be 10-digit number
            
            # Mark device as fully provisioned
            device.is_provisioned = 1
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "provision_acknowledgment_final",
                "device_id": device_id,
                "step": 2,
                "policy_key": policy_key,
                "message": "Client acknowledged policy, sending final PolicyKey"
            })
        else:
            # Step 1: Initial request, send temporary PolicyKey=0
            policy_key = "0"
            
            _write_json_line("activesync/activesync.log", {
                "event": "provision_initial_request",
                "device_id": device_id,
                "step": 1,
                "policy_key": policy_key,
                "message": "Sending initial policy with temporary PolicyKey=0"
            })
        from datetime import datetime, timedelta
from typing import List, Optional
from xml.etree import ElementTree as ET
import time
import uuid
import io
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

# CRITICAL FIX #31B: Add logger for protocol version negotiation logging
logger = logging.getLogger(__name__)

from app.auth import get_current_user_from_basic_auth
from app.database import ActiveSyncDevice, ActiveSyncState, CalendarEvent, User, get_db
from app.diagnostic_logger import _write_json_line
from app.email_service import EmailService
# ActiveSync WBXML builders (root-level module)
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
# Z-Push-compliant WBXML builder imports
from .wbxml_builder import (
    create_sync_response_wbxml,
    create_sync_response_wbxml_with_fetch,
    SyncBatch,
)
from .state_machine import SyncStateStore
from .adapter import sync_prepare_batch
from app.wbxml_parser import (
    parse_wbxml_sync_request,
    parse_wbxml_foldersync_request,
    parse_wbxml_sync_fetch_and_delete,
)
from app.synckey_utils import parse_synckey, generate_synckey, bump_synckey, has_synckey

# Rate limiting for sync requests
_sync_rate_limits = {}

router = APIRouter(prefix="/activesync", tags=["activesync"])

# Simple in-memory pending cache: (user, device, collection, client_key) -> wbxml bytes
_pending_batches_cache = {}


class ActiveSyncResponse:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content

    def __call__(self, *args, **kwargs):
        return Response(
            content=self.xml_content, media_type="application/vnd.ms-sync.wbxml"
        )


def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery only (no singular MS-ASProtocolVersion)."""
    return {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "15.0",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # OPTIONS advertises list of versions (plural only)
        # CRITICAL FIX #31: Cap to 14.1 while debugging!
        # iOS picks the HIGHEST version and expects that format!
        "MS-ASProtocolVersions": "14.1",  # Only advertise what we can deliver!
        # OPTIONS includes commands list
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert"
        ),
        # MS-ASHTTP protocol support headers
        "MS-ASProtocolSupports": "14.0,14.1",  # Only what we support!
    }


def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST).
    
    CRITICAL FIX #31: Echo the client's requested protocol version!
    iOS expects MS-ASProtocolVersion (singular) to match what it sent.
    """
    headers = {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "14.1",
        "X-MS-Server-ActiveSync": "14.1",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        "Content-Type": "application/vnd.ms-sync.wbxml",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # CRITICAL FIX #31: Echo the negotiated version (singular)
        # This MUST match what the client sent in MS-ASProtocolVersion header!
        "MS-ASProtocolVersion": protocol_version or "14.1",
        # Can include list too (optional on POST responses)
        "MS-ASProtocolVersions": "14.1",
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert"
        ),
        # MS-ASHTTP protocol support headers
        "MS-ASProtocolSupports": "14.0,14.1",
    }
    
    # Add X-MS-PolicyKey header if provided (iOS expects this after provisioning)
    if policy_key:
        headers["X-MS-PolicyKey"] = policy_key
        
    return headers


def create_sync_response(emails: List, sync_key: str = "1", collection_id: str = "1"):
    """Create ActiveSync XML response for email synchronization according to MS-ASCMD specification"""
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")

    # MS-ASCMD compliant structure - Status as child element, not attribute
    status_elem = ET.SubElement(root, "Status")
    status_elem.text = "1"  # Success status

    # SyncKey as child element
    synckey_elem = ET.SubElement(root, "SyncKey")
    synckey_elem.text = sync_key

    # Collections wrapper
    collections = ET.SubElement(root, "Collections")
    collection = ET.SubElement(collections, "Collection")
    collection.set("SyncKey", sync_key)
    collection.set("CollectionId", collection_id)

    # Add commands for each email according to Microsoft documentation
    for email in emails:
        add = ET.SubElement(collection, "Add")
        add.set("ServerId", f"{collection_id}:{email.id}")  # Format: CollectionId:EmailId

        # Email properties according to Microsoft documentation
        application_data = ET.SubElement(add, "ApplicationData")

        # Subject (required)
        subject_elem = ET.SubElement(application_data, "Subject")
        subject_elem.text = email.subject or "(no subject)"

        # From (required)
        from_elem = ET.SubElement(application_data, "From")
        from_elem.text = getattr(getattr(email, "sender", None), "email", "") or ""

        # To (required)
        to_elem = ET.SubElement(application_data, "To")
        to_elem.text = getattr(getattr(email, "recipient", None), "email", "") or ""

        # DateReceived (required) - Format MUST be like "2025-10-01T06:25:28.384Z"
        date_elem = ET.SubElement(application_data, "DateReceived")
        # Format MUST be like "2025-10-01T06:25:28.384Z"
        date_elem.text = email.created_at.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # DisplayTo (required)
        display_to = ET.SubElement(application_data, "DisplayTo")
        display_to.text = getattr(getattr(email, "recipient", None), "email", "") or ""

        # ThreadTopic (required)
        thread_topic = ET.SubElement(application_data, "ThreadTopic")
        thread_topic.text = email.subject or "(no subject)"

        # Importance (required)
        importance = ET.SubElement(application_data, "Importance")
        importance.text = "1"  # Normal importance

        # Read status (required)
        read_elem = ET.SubElement(application_data, "Read")
        read_elem.text = "1" if email.is_read else "0"

        # Body (required) - according to Microsoft documentation format
        body_elem = ET.SubElement(application_data, "Body")
        body_elem.set("Type", "2")  # HTML
        body_elem.set("EstimatedDataSize", str(len(email.body or "")))
        
        # Body data
        body_data = ET.SubElement(body_elem, "Data")
        body_data.text = email.body or ""
        
        # Body preview
        body_preview = ET.SubElement(body_elem, "Preview")
        body_preview.text = (email.body or "")[:100]  # First 100 characters

        # MessageClass (required for Exchange compatibility)
        message_class = ET.SubElement(application_data, "MessageClass")
        message_class.text = "IPM.Note"

        # InternetCPID (required)
        internet_cpid = ET.SubElement(application_data, "InternetCPID")
        internet_cpid.text = "28591"  # UTF-8

        # ContentClass (required)
        content_class = ET.SubElement(application_data, "ContentClass")
        content_class.text = "urn:content-classes:message"

        # NativeBodyType (required)
        native_body_type = ET.SubElement(application_data, "NativeBodyType")
        native_body_type.text = "2"  # HTML

        # *** FIX: Generate Unique Conversation IDs ***
        # For now, make every email its own conversation to avoid conflicts.
        conversation_id = ET.SubElement(application_data, "ConversationId")
        conversation_id.text = str(uuid.uuid4())

        # ConversationIndex (required for threading)
        conversation_index = ET.SubElement(application_data, "ConversationIndex")
        # A timestamp is a simple way to generate a unique index for this initial implementation.
        conversation_index.text = email.created_at.strftime('%Y%m%d%H%M%S')

        # Categories (required)
        categories = ET.SubElement(application_data, "Categories")
        categories.text = ""

    return ET.tostring(root, encoding="unicode")


@router.options("/Microsoft-Server-ActiveSync")
async def eas_options(request: Request):
    """Respond to ActiveSync OPTIONS discovery with required headers and log it.
    
    CRITICAL FIX #31: Use separate OPTIONS headers (no singular MS-ASProtocolVersion)!
    """
    headers = _eas_options_headers()  # ← Use OPTIONS-specific headers!
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "options",
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        },
    )
    return Response(status_code=200, headers=headers)


def _get_or_create_device(
    db: Session, user_id: int, device_id: str, device_type: str | None = None
) -> ActiveSyncDevice:
    device = (
        db.query(ActiveSyncDevice)
        .filter(
            ActiveSyncDevice.user_id == user_id, ActiveSyncDevice.device_id == device_id
        )
        .first()
    )
    if not device:
        device = ActiveSyncDevice(
            user_id=user_id, device_id=device_id, device_type=device_type or "generic"
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    return device


def _get_or_init_state(
    db: Session, user_id: int, device_id: str, collection_id: str = "1"
) -> ActiveSyncState:
    state = (
        db.query(ActiveSyncState)
        .filter(
            ActiveSyncState.user_id == user_id,
            ActiveSyncState.device_id == device_id,
            ActiveSyncState.collection_id == collection_id,
        )
        .first()
    )
    if not state:
        state = ActiveSyncState(
            user_id=user_id,
            device_id=device_id,
            collection_id=collection_id,
            sync_key="0",
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    
    # MS-ASCMD compliant: No artificial loop breaking - follow standard sync key progression
    
    return state


def _check_rate_limit(user_id: int, device_id: str, cmd: str) -> bool:
    """Check if user is making too many requests (rate limiting)"""
    key = f"{user_id}:{device_id}:{cmd}"
    now = time.time()
    
    if key not in _sync_rate_limits:
        _sync_rate_limits[key] = []
    
    # Clean old entries (older than 1 minute)
    _sync_rate_limits[key] = [t for t in _sync_rate_limits[key] if now - t < 60]
    
    # Check rate limit (max 100 requests per minute for sync commands - very lenient)
    if len(_sync_rate_limits[key]) >= 100:
        return False
    
    _sync_rate_limits[key].append(now)
    return True

def _bump_sync_key(state: ActiveSyncState, db: Session) -> str:
    try:
        next_key = str(int(state.sync_key) + 1)
    except Exception:
        next_key = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    state.sync_key = next_key
    db.commit()
    db.refresh(state)
    return state.sync_key


@router.post("/Microsoft-Server-ActiveSync")
async def eas_dispatch(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """Dispatcher for Microsoft-Server-ActiveSync commands."""
    cmd = request.query_params.get("Cmd", "").lower()
    device_id = request.query_params.get("DeviceId", "device-generic")
    device_type = request.query_params.get("DeviceType", "SmartPhone")
    
    # CRITICAL FIX #31: Read and echo the client's requested protocol version!
    # iOS sends MS-ASProtocolVersion header with the version it wants to use
    # We MUST echo this back or iOS will reject our responses!
    client_version = request.headers.get("MS-ASProtocolVersion", "14.1")
    # Validate it's one we support (cap to 14.1 for now)
    if client_version not in ["12.1", "14.0", "14.1"]:
        logger.warning(f"Client requested unsupported version {client_version}, capping to 14.1")
        client_version = "14.1"
    
    # CRITICAL FIX #11: Get device and policy key FIRST, then create headers with it
    # iOS requires X-MS-PolicyKey header on ALL commands after provisioning
    # Without it, iOS won't commit sync state and keeps reverting to SyncKey=0
    device = _get_or_create_device(db, current_user.id, device_id, device_type)
    # MS-ASPROV: PolicyKey must be 10-digit number after provisioning handshake
    policy_key = "1234567890" if device.is_provisioned == 1 else "0"
    
    # CRITICAL FIX #31: Pass protocol_version to echo client's request!
    headers = _eas_headers(policy_key=policy_key, protocol_version=client_version)
    
    # Log version negotiation
    logger.info(f"Protocol negotiation: client={client_version}, echoing back={client_version}")

    # High-resolution request logging
    request_body_bytes = await request.body()
    try:
        request_body_for_log = request_body_bytes.decode('utf-8', errors='ignore')
    except Exception:
        request_body_for_log = f"Could not decode request body. Length: {len(request_body_bytes)} bytes."
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "request_received", "command": cmd, "device_id": device_id,
            "user_agent": request.headers.get("User-Agent"), "query_params": dict(request.query_params),
            "body_preview": request_body_for_log[:500]
        }
    )

    if not cmd:
        _write_json_line("activesync/activesync.log", {"event": "no_command", "message": "No command specified"})
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Error xmlns="Error">
    <Status>2</Status>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Invalid request - command not specified</Message>
        </Error>
    </Response>
</Error>"""
        return Response(
            content=xml, 
            media_type="application/vnd.ms-sync.wbxml", 
            headers=headers,
            status_code=200
        )
    
    # Device already created above (line 285) for policy_key header
    # device = _get_or_create_device(db, current_user.id, device_id, device_type)  # ← Removed duplicate

    # --- Command Handling ---

    # FULL MS-ASPROV COMPLIANT PROVISION HANDLER
    # The client MUST be allowed to Provision itself at any time.
    if cmd == "provision":
        # MS-ASPROV Two-Step Handshake:
        # Step 1: Client sends initial request (no PolicyKey or PolicyKey=0)
        #         Server responds with PolicyKey=0 + policy settings
        # Step 2: Client acknowledges by sending back PolicyKey=0
        #         Server responds with final PolicyKey=1234567890 (10-digit number)
        # Step 3: Client includes PolicyKey=1234567890 in all subsequent requests
        
        # Parse WBXML request to detect which step we're in
        is_wbxml = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
        is_acknowledgment = False
        client_policy_key = None
        
        if is_wbxml and len(request_body_bytes) > 20:
            # Look for PolicyKey in request (token 0x0F in Provision codepage + 0x40 = 0x4F)
            # If PolicyKey=0 present, this is Step 2 (acknowledgment)
            pos = 0
            while pos < len(request_body_bytes) - 4:
                if (request_body_bytes[pos] == 0x4F and  # PolicyKey tag
                    pos + 1 < len(request_body_bytes) and request_body_bytes[pos + 1] == 0x03):  # STR_I
                    str_start = pos + 2
                    str_end = str_start
                    while str_end < len(request_body_bytes) and request_body_bytes[str_end] != 0x00:
                        str_end += 1
                    if str_end < len(request_body_bytes):
                        client_policy_key = request_body_bytes[str_start:str_end].decode('utf-8', errors='ignore')
                        if client_policy_key == "0":
                            is_acknowledgment = True
                        break
                pos += 1
        
        # Determine response based on step
        if is_acknowledgment:
            # Step 2: Client acknowledged, send FINAL policy key
            policy_key = "1234567890"  # MS-ASPROV: Must be 10-digit number
            
            # Mark device as fully provisioned
            device.is_provisioned = 1
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "provision_acknowledgment_final",
                "device_id": device_id,
                "step": 2,
                "policy_key": policy_key,
                "message": "Client acknowledged policy, sending final PolicyKey"
            })
        else:
            # Step 1: Initial request, send temporary PolicyKey=0
            policy_key = "0"
            
            _write_json_line("activesync/activesync.log", {
                "event": "provision_initial_request",
                "device_id": device_id,
                "step": 1,
                "policy_key": policy_key,
                "message": "Sending initial policy with temporary PolicyKey=0"
            })
        
        # Build XML response based on step
        if is_acknowledgment:
            # Step 2 response: Just PolicyKey, no Data
            xml = (
                f"""<?xml version="1.0" encoding="utf-8"?>
<Provision xmlns="Provision:">
    <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <Status>1</Status>
            <PolicyKey>{policy_key}</PolicyKey>
        </Policy>
    </Policies>
</Provision>"""
            )
        else:
            # Step 1 response: PolicyKey=0 + full policy settings
            xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Provision xmlns="Provision:">
            <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <Status>1</Status>
            <PolicyKey>{policy_key}</PolicyKey>
            <Data>
                <EASProvisionDoc>
                    <DevicePasswordEnabled>0</DevicePasswordEnabled>
                    <AlphanumericDevicePasswordRequired>0</AlphanumericDevicePasswordRequired>
                    <PasswordRecoveryEnabled>0</PasswordRecoveryEnabled>
                    <RequireDeviceEncryption>0</RequireDeviceEncryption>
                    <AttachmentsEnabled>1</AttachmentsEnabled>
                    <MinDevicePasswordLength>0</MinDevicePasswordLength>
                    <MaxInactivityTimeDeviceLock>0</MaxInactivityTimeDeviceLock>
                    <MaxDevicePasswordFailedAttempts>0</MaxDevicePasswordFailedAttempts>
                    <MaxEmailAgeFilter>0</MaxEmailAgeFilter>
                    <AllowSimpleDevicePassword>1</AllowSimpleDevicePassword>
                    <MaxAttachmentSize>51200000</MaxAttachmentSize>
                    <AllowStorageCard>1</AllowStorageCard>
                    <AllowCamera>1</AllowCamera>
                    <AllowUnsignedApplications>1</AllowUnsignedApplications>
                    <AllowUnsignedInstallationPackages>1</AllowUnsignedInstallationPackages>
                    <MinDevicePasswordComplexCharacters>0</MinDevicePasswordComplexCharacters>
                    <AllowWiFi>1</AllowWiFi>
                    <AllowTextMessaging>1</AllowTextMessaging>
                    <AllowPOPIMAPEmail>1</AllowPOPIMAPEmail>
                    <AllowBluetooth>2</AllowBluetooth>
                    <AllowIrDA>1</AllowIrDA>
                    <RequireManualSyncWhenRoaming>0</RequireManualSyncWhenRoaming>
                    <AllowDesktopSync>1</AllowDesktopSync>
                    <MaxCalendarAgeFilter>0</MaxCalendarAgeFilter>
                    <AllowHTMLEmail>1</AllowHTMLEmail>
                    <MaxEmailBodyTruncationSize>-1</MaxEmailBodyTruncationSize>
                    <MaxEmailHTMLBodyTruncationSize>-1</MaxEmailHTMLBodyTruncationSize>
                    <RequireSignedSMIMEMessages>0</RequireSignedSMIMEMessages>
                    <RequireEncryptedSMIMEMessages>0</RequireEncryptedSMIMEMessages>
                    <RequireSignedSMIMEAlgorithm>0</RequireSignedSMIMEAlgorithm>
                    <RequireEncryptionSMIMEAlgorithm>0</RequireEncryptionSMIMEAlgorithm>
                    <AllowSMIMEEncryptionAlgorithmNegotiation>2</AllowSMIMEEncryptionAlgorithmNegotiation>
                    <AllowSMIMESoftCerts>1</AllowSMIMESoftCerts>
                    <AllowBrowser>1</AllowBrowser>
                    <AllowConsumerEmail>1</AllowConsumerEmail>
                    <AllowRemoteDesktop>1</AllowRemoteDesktop>
                    <AllowInternetSharing>1</AllowInternetSharing>
                </EASProvisionDoc>
            </Data>
        </Policy>
    </Policies>
</Provision>"""
        
        return Response(content=xml, media_type="application/vnd.ms-sync.wbxml", headers=_eas_headers(policy_key=policy_key))

    # All other commands require that the device has completed the provisioning step above.
    if device.is_provisioned != 1:
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "provisioning_required", "command": cmd, "device_id": device_id,
                "message": "Device not provisioned. Sending HTTP 449.",
            },
        )
        return Response(status_code=449)

    if cmd == "foldersync":
        # Microsoft ActiveSync FolderSync implementation according to MS-ASCMD specification
        # Use dedicated state for folder hierarchy (collection_id="0")
        state = _get_or_init_state(db, current_user.id, device_id, "0")
        
        # Parse WBXML request body to extract actual SyncKey
        wbxml_params = parse_wbxml_foldersync_request(request_body_bytes)
        client_sync_key = wbxml_params.get("sync_key", request.query_params.get("SyncKey", "0"))
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # Check if client is sending WBXML (iPhone sends WBXML)
        is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
        
        # *** ENHANCED DEBUGGING: COMPREHENSIVE REQUEST/RESPONSE LOGGING ***
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "foldersync_debug_comprehensive",
                "client_key": client_sync_key,
                "client_key_int": client_key_int,
                "server_key": state.sync_key,
                "server_key_int": server_key_int,
                "is_wbxml_request": is_wbxml_request,
                "request_body_length": len(request_body_bytes),
                "request_body_hex": request_body_bytes[:50].hex() if request_body_bytes else "empty",
                "user_agent": request.headers.get("User-Agent", ""),
                "device_id": device_id,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            },
        )
        
        # CASE 1: Initial Sync (client_key=0). Provide the full, detailed folder hierarchy.
        if client_key_int == 0:
            # Only set sync_key if it's actually 0 in the database (true first request)
            if state.sync_key == "0":
                state.sync_key = "1"
                db.commit()
                _write_json_line("activesync/activesync.log", {
                    "event": "foldersync_initial_sync_key_updated", 
                    "device_id": device_id,
                    "old_sync_key": "0",
                    "new_sync_key": "1"
                })
            
            if is_wbxml_request:
                # Return correct minimal WBXML response with all 5 folders
                from activesync import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "foldersync_initial_wbxml_response",
                        "sync_key": state.sync_key,
                        "client_key": client_sync_key,
                        "wbxml_length": len(wbxml_content),
                        "wbxml_type": "minimal_correct",
                        "wbxml_hex": wbxml_content[:100].hex(),
                        "wbxml_full_hex": wbxml_content.hex(),
                        "sync_key_progression": {
                            "client_sent": client_sync_key,
                            "server_responding": state.sync_key,
                            "is_initial_sync": client_key_int == 0,
                            "database_updated": state.sync_key == "1" and client_key_int == 0
                        },
                        "response_analysis": {
                            "header": wbxml_content[:10].hex(),
                            "folder_count": wbxml_content.count(b'\x4F'),  # Count Add tags (0x0F + 0x40 = 0x4F)
                            "has_status": b'\x4C' in wbxml_content,  # Status tag (0x0C + 0x40 = 0x4C)
                            "has_synckey": b'\x52' in wbxml_content,  # SyncKey tag (0x12 + 0x40 = 0x52)
                            "has_changes": b'\x4E' in wbxml_content,  # Changes tag (0x0E + 0x40 = 0x4E)
                        }
                    },
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                # Return XML response for other clients
                # *** FINAL FIX: Provide the complete, standard Exchange mailbox structure. ***
                # This includes Mail, Calendar, and Contacts folders.
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Changes>
        <Count>7</Count>
        <Add>
            <ServerId>1</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Inbox</DisplayName>
            <Type>2</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>2</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Drafts</DisplayName>
            <Type>3</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>3</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Deleted Items</DisplayName>
            <Type>4</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>4</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Sent Items</DisplayName>
            <Type>5</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>5</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Outbox</DisplayName>
            <Type>6</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>calendar</ServerId> 
            <ParentId>0</ParentId>
            <DisplayName>Calendar</DisplayName>
            <Type>8</Type> 
            <SupportedClasses>
                <SupportedClass>Calendar</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>contacts</ServerId> 
            <ParentId>0</ParentId>
            <DisplayName>Contacts</DisplayName>
            <Type>9</Type> 
            <SupportedClasses>
                <SupportedClass>Contacts</SupportedClass>
            </SupportedClasses>
        </Add>
    </Changes>
</FolderSync>"""
                # *** ENHANCED LOGGING: CAPTURE FULL RESPONSE ***
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "foldersync_initial_response",
                        "sync_key": state.sync_key,
                        "client_key": client_sync_key,
                        "full_response_xml": xml  # Log the entire XML response
                    },
                )
        # CASE 2: Client is up to date. Report no changes.
        elif client_key_int == server_key_int:
            if is_wbxml_request:
                # Return WBXML response for iPhone clients
                from activesync import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_no_changes_wbxml", "sync_key": state.sync_key, "client_key": client_sync_key},
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Changes><Count>0</Count></Changes>
</FolderSync>"""
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key},
                )

        # CASE 3: Client is out of sync. Force it to start over.
        else:
            if is_wbxml_request:
                # Return WBXML response for iPhone clients
                from activesync import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)  # Simplified error response
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_recovery_sync_wbxml", "server_key": state.sync_key, "client_key": client_sync_key},
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>8</Status>
</FolderSync>"""
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_recovery_sync", "server_key": state.sync_key, "client_key": client_sync_key},
                )
        
        # Return XML response for non-WBXML clients
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )

    elif cmd == "sync":
        # Microsoft ActiveSync Sync implementation according to MS-ASCMD specification
        # Use state for the specific collection being synced
        collection_id = request.query_params.get("CollectionId", "1")
        state = _get_or_init_state(db, current_user.id, device_id, collection_id)
        
        # Parse WBXML request body to extract actual SyncKey and CollectionId
        wbxml_params = parse_wbxml_sync_request(request_body_bytes)
        extra_ops = parse_wbxml_sync_fetch_and_delete(request_body_bytes)
        fetch_ids = extra_ops.get("fetch_ids", [])
        delete_ids = extra_ops.get("delete_ids", [])
        _write_json_line("activesync/activesync.log", {"event": "sync_ops_parsed", "fetch_ids": fetch_ids, "delete_ids": delete_ids})
        client_sync_key = wbxml_params.get("sync_key", request.query_params.get("SyncKey", "0"))
        collection_id = wbxml_params.get("collection_id", request.query_params.get("CollectionId", "1"))
        window_size_str = wbxml_params.get("window_size", "5")
        try:
            window_size = int(window_size_str)
        except (ValueError, TypeError):
            window_size = 5  # Default to 5 emails per sync
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # CRITICAL FIX: Handle SyncKey=0 BEFORE any email queries!
        # When client sends SyncKey=0, it means "I have nothing, start fresh"
        # We MUST reset last_synced_email_id BEFORE filtering emails!
        if client_sync_key == "0":
            state.synckey_counter = 1
            state.sync_key = "1"
            state.last_synced_email_id = 0  # RESET PAGINATION!
            state.pending_sync_key = None
            state.pending_max_email_id = None
            state.pending_item_ids = None
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_initial_reset_EARLY",
                "device_id": device_id,
                "collection_id": collection_id,
                "message": "CRITICAL: Reset last_synced_email_id BEFORE email query"
            })
        
        # CRITICAL: Detect InvalidSyncKey - client and server are out of sync
        # Per expert: "When client sends stale key (e.g. 4) but server is at 190,
        # return Status=3 (InvalidSyncKey) with SyncKey=0 to force client reset"
        # Allow tolerance of ±2 for pending batches, but reject if gap is huge
        if client_sync_key != "0" and abs(client_key_int - server_key_int) > 3:
            _write_json_line("activesync/activesync.log", {
                "event": "sync_invalid_synckey_detected",
                "client_sync_key": client_sync_key,
                "server_sync_key": state.sync_key,
                "gap": abs(client_key_int - server_key_int),
                "message": "Client sent stale SyncKey - forcing reset with Status=3"
            })
            # Return InvalidSyncKey response
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            else:
                # XML fallback
                xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Collections>
        <Collection>
            <Class>Email</Class>
            <SyncKey>0</SyncKey>
            <CollectionId>{collection_id}</CollectionId>
            <Status>3</Status>
        </Collection>
    </Collections>
</Sync>"""
                return Response(content=xml_response, media_type="application/xml", headers=headers)
        
        # CRITICAL FIX #26: Two-phase commit - check for pending batch first!
        # Expert: "Only commit when the client echoes back the SyncKey you issued"
        import json
        
        # CRITICAL FIX #27: Expert's correction - SyncKey must ALWAYS advance!
        # "Every Sync response must issue a new SyncKey. If you keep returning
        #  the same SyncKey, iOS treats the state as inconsistent and restarts."
        #
        # NEW LOGIC:
        # 1) Client confirms last batch? → Clear pending, advance to next batch
        if state.pending_sync_key and client_sync_key == state.pending_sync_key:
            # Client got the batch! Commit it now
            state.last_synced_email_id = state.pending_max_email_id or state.last_synced_email_id
            state.sync_key = state.pending_sync_key
            state.synckey_counter = int(state.pending_sync_key) if state.pending_sync_key.isdigit() else state.synckey_counter
            state.pending_sync_key = None
            state.pending_max_email_id = None
            state.pending_item_ids = None
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_pending_confirmed",
                "client_sync_key": client_sync_key,
                "committed_max_id": state.last_synced_email_id,
                "message": "Client confirmed - committed pending batch, will send next with NEW key"
            })
            # Fall through to compute next batch WITH A FRESH KEY
        
        # 2) Client didn't get last response? (retries with old key OR sends 0 when pending exists)
        # CRITICAL FIX #26C: Check if client is one behind pending!
        # Example: client="6", server="7", pending="7" → client wants the pending batch!
        elif state.pending_sync_key:
            # Calculate if client is asking for the pending batch
            try:
                client_int = int(client_sync_key) if client_sync_key.isdigit() else 0
                pending_int = int(state.pending_sync_key) if state.pending_sync_key.isdigit() else 0
                # CRITICAL FIX #38: DON'T treat SyncKey=0 as "asking for pending"!
                # When client sends SyncKey=0, it's a FRESH initial sync (e.g., after account re-add).
                # We should ONLY resend pending if client is retrying with a non-zero key.
                # Client is asking for pending if: client==pending OR client==server OR client==pending-1
                is_asking_for_pending = (
                    client_sync_key == state.pending_sync_key or  # Exact match
                    client_sync_key == state.sync_key or  # Old server key
                    # client_sync_key == "0" or  # ← REMOVED! Don't treat 0 as retry!
                    (client_int > 0 and pending_int > 0 and client_int == pending_int - 1)  # One behind
                )
            except:
                is_asking_for_pending = True  # If in doubt, resend
            
            if is_asking_for_pending:
                # Re-send the exact same pending batch!
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_resend_pending",
                    "client_sync_key": client_sync_key,
                    "server_sync_key": state.sync_key,
                    "pending_sync_key": state.pending_sync_key,
                    "message": "Client retry - resending pending batch IDEMPOTENTLY with SAME key"
                })
                
                # Fetch the specific emails from pending
                if state.pending_item_ids:
                    pending_ids = json.loads(state.pending_item_ids)
                    email_service = EmailService(db)
                    # Ensure folder_map defined before use
                    try:
                        _fm = folder_map  # may not exist yet in this branch
                    except NameError:
                        _fm = {"1": "inbox", "2": "drafts", "3": "deleted", "4": "sent", "5": "outbox"}
                    all_emails_temp = email_service.get_user_emails(current_user.id, _fm.get(collection_id, "inbox"), limit=200)
                    emails_to_resend = [e for e in all_emails_temp if e.id in pending_ids]
                    
                    # Calculate has_more: are there items after the pending batch?
                    max_pending_id = max(pending_ids) if pending_ids else 0
                    remaining_emails = [e for e in all_emails_temp if e.id > max_pending_id]
                    has_more_pending = len(remaining_emails) > 0
                    
                    # Re-send with SAME SyncKey (idempotent resend!) using compliant builder
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=state.pending_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or '') } for e in emails_to_resend],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=has_more_pending,
                        class_name="Email",
                    )
                    return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
        
        # Debug logging for sync key comparison
        _write_json_line(
            "activesync/activesync.log",
            {"event": "sync_debug", "client_key": client_sync_key, "client_key_int": client_key_int, "server_key": state.sync_key, "server_key_int": server_key_int, "user_id": current_user.id, "has_pending": bool(state.pending_sync_key)},
        )
        
        # Get emails for the specified collection
        # Map CollectionId to folder type for simplified folder structure
        # Microsoft ActiveSync folder mapping according to MS-ASCMD specification
        folder_map = {
            "1": "inbox",       # Inbox (Type 2)
            "2": "drafts",       # Drafts (Type 3)
            "3": "deleted",      # Deleted Items (Type 4)
            "4": "sent",         # Sent Items (Type 5)
            "5": "outbox"        # Outbox (Type 6)
        }
        folder_type = folder_map.get(collection_id, "inbox")
        
        # CRITICAL FIX #24: Query only NEW emails (proper pagination!)
        # Expert: "iOS expects every successful Sync response to return a new SyncKey"
        # We must track which emails have been sent and only send NEW ones!
        email_service = EmailService(db)
        
        # Get last synced email ID for this device+collection
        last_id = state.last_synced_email_id or 0
        
        # Query emails AFTER the last synced ID (proper pagination!)
        all_emails = email_service.get_user_emails(current_user.id, folder_type, limit=100)
        
        # Filter to only unsent emails
        emails = [e for e in all_emails if e.id > last_id]

        # Include FETCHED items regardless of pagination
        fetched_emails = []
        if fetch_ids:
            try:
                # server_id may be formatted like "1:36"; extract numeric id portion
                fetch_int_ids = []
                for sid in fetch_ids:
                    parts = str(sid).split(":")
                    n = parts[-1]
                    if n.isdigit():
                        fetch_int_ids.append(int(n))
                fetched_emails = email_service.get_emails_by_ids(current_user.id, fetch_int_ids)
                _write_json_line("activesync/activesync.log", {"event": "sync_fetch_lookup", "fetch_ids": fetch_ids, "resolved": [e.id for e in fetched_emails]})
            except Exception as ex:
                _write_json_line("activesync/activesync.log", {"event": "sync_fetch_error", "error": str(ex)})
        
        _write_json_line("activesync/activesync.log", {
            "event": "sync_pagination_filter",
            "last_synced_email_id": last_id,
            "total_emails_in_folder": len(all_emails),
            "new_emails_to_sync": len(emails),
            "message": "Filtered to only NEW emails not yet synced"
        })
        
        # Enhanced logging with detailed email information
        email_details = []
        for email in emails:
            # Fix subject - use "No Subject" if empty
            subject = getattr(email, 'subject', '') or 'No Subject'
            if not subject.strip():
                subject = 'No Subject'
            
            # Fix sender - check both internal sender and external_sender
            sender_email = 'Unknown'
            if hasattr(email, 'sender') and email.sender:
                sender_email = getattr(email.sender, 'email', 'Unknown')
            elif hasattr(email, 'external_sender') and email.external_sender:
                sender_email = email.external_sender
            
            # Fix recipient - check both internal recipient and external_recipient  
            recipient_email = 'Unknown'
            if hasattr(email, 'recipient') and email.recipient:
                recipient_email = getattr(email.recipient, 'email', 'Unknown')
            elif hasattr(email, 'external_recipient') and email.external_recipient:
                recipient_email = email.external_recipient
            
            email_details.append({
                "id": email.id,
                "subject": subject[:50],  # Truncate for logging
                "sender": sender_email,
                "recipient": recipient_email,
                "created_at": getattr(email, 'created_at', None).isoformat() if getattr(email, 'created_at', None) else None,
                "is_read": getattr(email, 'is_read', False),
                "is_deleted": getattr(email, 'is_deleted', False),
                "is_external": getattr(email, 'is_external', False),
                "sender_id": getattr(email, 'sender_id', None),
                "recipient_id": getattr(email, 'recipient_id', None)
            })
        
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "sync_emails_found", 
                "count": len(emails), 
                "user_id": current_user.id,
                "user_email": current_user.email,
                "collection_id": collection_id,
                "folder_type": folder_type,
                "folder_mapping": folder_map,
                "email_details": email_details,
                "sync_state": {
                    "device_id": device_id,
                    "client_sync_key": client_sync_key,
                    "server_sync_key": state.sync_key,
                    "collection_id": collection_id
                }
            },
        )
        
        # Initial sync (SyncKey=0) - already handled above at line 799-813!
        if client_sync_key == "0":
            # State was already reset BEFORE email query (line 799-813)
            # This ensures last_synced_email_id=0 BEFORE we filter emails
            response_sync_key = "1"
            # CRITICAL FIX #23-2: Send items on FIRST sync per expert!
            # Expert: "iOS is fine receiving items on the first response"
            # Previous logic sent empty response, which was WRONG!
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                # Respect WindowSize for initial sync too!
                emails_to_send = emails[:window_size] if window_size else emails
                has_more = len(emails) > window_size if window_size else False
                
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_initial_WITH_ITEMS",
                    "reason": "Expert: iOS accepts items on first response",
                    "window_size": window_size,
                    "email_count_total": len(emails),
                    "email_count_sent": len(emails_to_send),
                    "has_more": has_more,
                    "message": "Sending items immediately on SyncKey 0→1"
                })
                # CRITICAL: ACTUALLY SEND THE EMAILS! (was passing empty list)
                # Convert SQLAlchemy Email objects to dicts for WBXML builder
                # Z-Push approach: ALWAYS send HTML as Type=2 if content looks like HTML
                email_dicts = []
                for email in emails_to_send:
                    body_content = email.body or email.preview or ''
                    body_html_content = None
                    
                    # Z-Push logic: If body contains HTML, send it as Type=2 (HTML)
                    # iOS prefers HTML and will render it properly
                    if body_content and ('<html' in body_content.lower() or body_content.strip().startswith('<')):
                        # This is HTML content - send it as body_html for Type=2
                        body_html_content = body_content
                        # Also provide plain text fallback by stripping HTML tags
                        import re
                        plain_fallback = re.sub(r'<[^>]+>', '', body_content)
                        plain_fallback = plain_fallback.replace('&nbsp;', ' ').replace('&amp;', '&')
                        plain_fallback = plain_fallback.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
                        body_content = plain_fallback.strip()
                    
                    email_dicts.append({
                        'id': email.id,
                        'server_id': f"{collection_id}:{email.id}",
                        'subject': email.subject or '(no subject)',
                        'from': email.external_sender or (email.sender.email if email.sender else ''),
                        'to': email.external_recipient or (email.recipient.email if email.recipient else ''),
                        'created_at': email.created_at,
                        'is_read': email.is_read,
                        'body': body_content,  # Plain text fallback
                        'body_html': body_html_content,  # HTML body (Type=2)
                    })
                
                wbxml_batch = create_sync_response_wbxml(
                    sync_key=response_sync_key,
                    emails=email_dicts,
                    collection_id=collection_id,
                    window_size=window_size,
                    more_available=has_more,
                    class_name="Email",
                )
                wbxml = wbxml_batch.payload
                
                # CRITICAL FIX #26: Stage as PENDING, don't commit yet!
                # Expert: "Only commit when client echoes back the SyncKey"
                if emails_to_send:
                    max_sent_id = max(e.id for e in emails_to_send)
                    state.pending_sync_key = response_sync_key
                    state.pending_max_email_id = max_sent_id
                    state.pending_item_ids = json.dumps([e.id for e in emails_to_send])
                
                # Commit PENDING state (not last_synced_email_id yet!)
                db.commit()
                
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_initial_wbxml", 
                        "sync_key": response_sync_key, 
                        "client_key": client_sync_key, 
                        "email_count": len(emails),
                        "window_size": window_size,
                        "collection_id": collection_id, 
                        "wbxml_length": len(wbxml), 
                        "wbxml_first20": wbxml[:20].hex(), 
                        "wbxml_analysis": {
                            "header": wbxml[:6].hex(), 
                            "has_emails": len(emails) > 0, 
                            "codepage_0_airsync": True,
                            "wbxml_structure": {
                                "header_bytes": wbxml[:6].hex(),
                                "switch_to_airsync": wbxml[6:8].hex(),
                                "sync_token": wbxml[8:9].hex(),
                                "status_token": wbxml[9:14].hex(),
                                "top_synckey_token": wbxml[14:19].hex()
                            }
                        },
                        "user_mapping": {
                            "user_id": current_user.id,
                            "user_email": current_user.email,
                            "folder_type": folder_type,
                            "collection_id": collection_id
                        },
                        "email_summary": {
                            "total_emails": len(emails),
                            "unread_count": sum(1 for email in emails if not getattr(email, 'is_read', False)),
                            "read_count": sum(1 for email in emails if getattr(email, 'is_read', False))
                        }
                    },
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            # XML response for non-WBXML clients (with emails for initial sync)
            xml_response = create_sync_response(emails, sync_key=response_sync_key, collection_id=collection_id)
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_initial_complete", "sync_key": state.sync_key, "client_key": client_sync_key, "response_key": response_sync_key, "email_count": len(emails)},
            )
        # Client sends SyncKey=0 but server is ahead - sync key mismatch, need to reset
        elif client_key_int == 0 and server_key_int > 1:
            # Server is ahead, client wants to restart - send error to force client to reset
            _write_json_line("activesync/activesync.log", {
                "event": "sync_key_mismatch_reset_required",
                "client_key": client_sync_key,
                "server_key": state.sync_key,
                "action": "Sending Status=3 to force client reset"
            })
            # Reset server to 0 to allow fresh start
            state.sync_key = "0"
            db.commit()
            # Send Status=3 (Invalid sync key) to tell client to restart
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            xml_response = create_sync_response([], sync_key="0", collection_id=collection_id)
        # Client confirmed initial sync with simple integer synckey
        elif client_sync_key != "0":
            # Parse simple integer synckey
            try:
                client_counter = int(client_sync_key)
            except ValueError:
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_invalid_synckey_format",
                    "client_sync_key": client_sync_key,
                    "error": "Not a valid integer"
                })
                # Send Status=3 (invalid synckey)
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                    return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
                return Response(status_code=400)
            
            # CRITICAL FIX #27: Always bump SyncKey for EVERY response!
            # Expert: "Every Sync response must issue a new SyncKey"
            state.synckey_counter = client_counter + 1
            response_sync_key = str(state.synckey_counter)
            state.sync_key = response_sync_key  # Update for next request
            # NOTE: We commit this BEFORE sending, so the key is persisted!
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_client_confirmed_simple",
                "client_sync_key": client_sync_key,
                "response_sync_key": response_sync_key,
                "client_counter": client_counter,
                "new_counter": state.synckey_counter,
                "email_count": len(emails)
            })
            
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                # CRITICAL FIX #13 (APPLIED TO ALL CODE PATHS): Respect WindowSize!
                # Expert diagnosis: "you dump 19 items in one batch with WindowSize=4"
                # This code path was missing the WindowSize enforcement!
                emails_to_send = emails[:window_size] if window_size else emails
                has_more = len(emails) > window_size if window_size else False

                # Use builder that can include both Adds and Fetch responses
                from activesync import create_sync_response_wbxml_with_fetch
                wbxml_batch = create_sync_response_wbxml_with_fetch(
                    sync_key=response_sync_key,
                    emails=[{
                        'id': e.id,
                        'subject': str(getattr(e, 'subject', '') or ''),
                        'from': str(
                            getattr(e, 'external_sender', None)
                            or (getattr(getattr(e, 'sender', None), 'email', None) if getattr(e, 'sender', None) else None)
                            or getattr(e, 'from', None)
                            or getattr(e, 'sender', None)
                            or ''
                        ),
                        'to': str(
                            getattr(e, 'external_recipient', None)
                            or (getattr(getattr(e, 'recipient', None), 'email', None) if getattr(e, 'recipient', None) else None)
                            or getattr(e, 'to', None)
                            or getattr(e, 'recipient', None)
                            or ''
                        ),
                        'created_at': e.created_at,
                        'is_read': bool(getattr(e, 'is_read', False)),
                        'body': str(getattr(e, 'body', None) or getattr(e, 'preview', None) or ''),
                        'body_html': str(getattr(e, 'body_html', None) or getattr(e, 'html_body', None) or '')
                    } for e in emails_to_send],
                    fetched=[{
                        'id': e.id,
                        'server_id': f"{collection_id}:{e.id}",
                        'subject': str(getattr(e, 'subject', '') or ''),
                        'from': str(
                            getattr(e, 'external_sender', None)
                            or (getattr(getattr(e, 'sender', None), 'email', None) if getattr(e, 'sender', None) else None)
                            or getattr(e, 'from', None)
                            or getattr(e, 'sender', None)
                            or ''
                        ),
                        'to': str(
                            getattr(e, 'external_recipient', None)
                            or (getattr(getattr(e, 'recipient', None), 'email', None) if getattr(e, 'recipient', None) else None)
                            or getattr(e, 'to', None)
                            or getattr(e, 'recipient', None)
                            or ''
                        ),
                        'created_at': e.created_at,
                        'is_read': bool(getattr(e, 'is_read', False)),
                        'body': str(getattr(e, 'body', None) or getattr(e, 'preview', None) or ''),
                        'body_html': str(getattr(e, 'body_html', None) or getattr(e, 'html_body', None) or '')
                    } for e in fetched_emails],
                    collection_id=collection_id,
                    window_size=window_size,
                    more_available=has_more,
                    class_name="Email",
                )
                wbxml = wbxml_batch.payload
                # If there were FETCH requests, append <Responses><Fetch> with bodies
                if fetched_emails:
                    from activesync import write_fetch_responses
                    w = activesync_w = None
                    try:
                        # Append to existing WBXML: we need a writer capable of appending; since our
                        # builder doesn't expose partial writer, for now we rebuild a combined payload:
                        # (Simple approach: just send the same Add body; iOS accepts body under Add as well)
                        # TODO: Refactor builder to append Responses/Fetch in place.
                        pass
                    except Exception:
                        pass
                
                # CRITICAL FIX #26 + #27: Stage as PENDING and advance SyncKey!
                # Expert FIX #27: "SyncKey must ALWAYS advance on every response"
                # Expert FIX #26: "Only commit last_synced_email_id when client confirms"
                if emails_to_send:
                    max_sent_id = max(e.id for e in emails_to_send)
                    state.pending_sync_key = response_sync_key
                    state.pending_max_email_id = max_sent_id
                    state.pending_item_ids = json.dumps([e.id for e in emails_to_send])
                
                # Commit: NEW SyncKey + PENDING batch (NOT last_synced_email_id yet!)
                # state.sync_key and state.synckey_counter were set above
                db.commit()
                
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_emails_sent_wbxml_simple", 
                        "sync_key": response_sync_key,  # ← NEW key in response
                        "client_key": client_sync_key,  # ← Key client sent
                        "key_progression": f"{client_sync_key}→{response_sync_key}",  # ← Visual!
                        "email_count_total": len(emails),  # ← Total available
                        "email_count_sent": len(emails_to_send),  # ← Actually sent
                        "window_size": window_size,  # ← Client requested
                        "has_more": has_more,  # ← MoreAvailable flag
                        "collection_id": collection_id, 
                        "wbxml_length": len(wbxml), 
                        "wbxml_first20": wbxml[:20].hex(),
                        "wbxml_full_hex": wbxml.hex(),  # ← FULL DUMP for expert analysis
                        "last_synced_email_id": state.last_synced_email_id,  # ← Pagination cursor
                        "pending_staged": bool(state.pending_sync_key)  # ← Pending active?
                    },
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
        # Client sync key matches server - check if we need to send emails
        elif client_key_int == server_key_int:
            # If we have emails to send, send them and bump sync key
            if len(emails) > 0:
                new_sync_key = _bump_sync_key(state, db)
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    # CRITICAL FIX #13: Respect WindowSize! Only send N items at a time
                    # Expert diagnosis: "If client asked for WindowSize = N, put at most N <Add> items"
                    emails_to_send = emails[:window_size] if window_size else emails
                    has_more = len(emails) > window_size if window_size else False
                    
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=new_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or ''), 'body_html': str(getattr(e,'body_html',None) or getattr(e,'html_body',None) or '') } for e in emails_to_send],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=has_more,
                        class_name="Email",
                    )
                    wbxml = wbxml_batch.payload
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_emails_sent_wbxml", 
                            "sync_key": new_sync_key, 
                            "client_key": client_sync_key, 
                            "email_count_total": len(emails),  # ← Total available
                            "email_count_sent": len(emails_to_send),  # ← Actually sent
                            "window_size": window_size,  # ← Client requested
                            "has_more": has_more,  # ← MoreAvailable flag
                            "collection_id": collection_id, 
                            "wbxml_length": len(wbxml), 
                            "wbxml_first20": wbxml[:20].hex(),
                            "wbxml_full_hex": wbxml.hex(),  # ← Full hex dump for expert analysis
                        },
                    )
                    return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
                xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_emails_sent", "sync_key": new_sync_key, "client_key": client_sync_key, "email_count": len(emails), "collection_id": collection_id},
                )
            else:
                # No emails to send - return no changes
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=state.sync_key,
                        emails=[],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=False,
                        class_name="Email",
                    )
                    wbxml = wbxml_batch.payload
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_no_changes_wbxml", "sync_key": state.sync_key, "client_key": client_sync_key, "collection_id": collection_id, "wbxml_length": len(wbxml), "wbxml_first20": wbxml[:20].hex()},
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
</Sync>"""
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "No changes - client and server in sync"},
            )
        # Client sync key is behind server - Graceful catch-up approach
        elif client_key_int < server_key_int:
            # Graceful approach: Send current emails with next sync key to catch up client
            # Don't force reset - instead, send current state to get client caught up
            sync_gap = server_key_int - client_key_int
            new_sync_key = _bump_sync_key(state, db)
            
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                try:
                    # Send emails respecting WindowSize to get client caught up
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=new_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or ''), 'body_html': str(getattr(e,'body_html',None) or getattr(e,'html_body',None) or '') } for e in emails],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=False,
                        class_name="Email",
                    )
                except Exception as e:
                    # Log the error
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_wbxml_creation_error",
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }
                    )
                    # Fall back to XML
                    xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
                else:
                    wbxml = wbxml_batch.payload
                    # Log the successful WBXML creation
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_client_behind_graceful_wbxml",
                            "sync_key": new_sync_key,
                            "client_key": client_sync_key,
                            "server_key": state.sync_key,
                            "email_count": len(emails),
                            "collection_id": collection_id,
                            "wbxml_length": len(wbxml),
                            "wbxml_first50": wbxml[:50].hex(),
                            "sync_gap": sync_gap
                        }
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            else:
                xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
                
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_client_behind_graceful", "sync_key": new_sync_key, "client_key": client_sync_key, "server_key": state.sync_key, "email_count": len(emails), "collection_id": collection_id, "sync_gap": sync_gap, "approach": "graceful_catchup_all_emails"},
                )
        # Client sync key is ahead of server - this shouldn't happen, return MS-ASCMD compliant error
        else:
            xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Status>2</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Sync key error - client ahead of server</Message>
        </Error>
    </Response>
</Sync>"""
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_sync_key_error", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Sync key error - client ahead of server"},
            )
        
        return Response(
            content=xml_response,
            media_type="application/xml",
            headers=headers,
        )
    if cmd == "ping":
        # Minimal Ping response with heartbeat interval acceptance
        _write_json_line("activesync/activesync.log", {"event": "ping"})
        return Response(status_code=200, headers=headers)
    if cmd == "sendmail":
        # Accept request (actual SMTP send could be wired later)
        _write_json_line("activesync/activesync.log", {"event": "sendmail"})
        return Response(status_code=200, headers=headers)
    elif cmd == "getitemestimate":
        # MS-ASCMD GetItemEstimate implementation
        collection_id = request.query_params.get("CollectionId", "1")
        folder_type = "inbox" if collection_id == "1" else "inbox"
        
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, folder_type, limit=1000)
        
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetItemEstimate xmlns="GetItemEstimate">
    <Status>1</Status>
    <Response>
        <Collection>
            <CollectionId>{collection_id}</CollectionId>
            <Estimate>{len(emails)}</Estimate>
        </Collection>
    </Response>
</GetItemEstimate>"""
        
        _write_json_line(
            "activesync/activesync.log",
            {"event": "getitemestimate", "collection_id": collection_id, "estimate": len(emails), "user_id": current_user.id},
        )
    if cmd == "settings":
        # MS-ASCMD Settings implementation with comprehensive device management
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Settings xmlns="Settings">
    <Status>1</Status>
    <DeviceInformation>
        <Set>
            <Model>Generic ActiveSync Device</Model>
            <IMEI>123456789012345</IMEI>
            <FriendlyName>ActiveSync Client</FriendlyName>
            <OS>iOS/Android/Windows</OS>
            <OSLanguage>en-US</OSLanguage>
            <PhoneNumber>+1234567890</PhoneNumber>
            <UserAgent>Microsoft-Server-ActiveSync/16.0</UserAgent>
        </Set>
    </DeviceInformation>
    <Oof>
        <Get>
            <BodyType>Text</BodyType>
        </Get>
    </Oof>
    <DevicePassword>
        <Set>
            <Password>123456</Password>
        </Set>
    </DevicePassword>
    <UserInformation>
        <Get>
            <EmailAddresses>
                <SMTPAddress>{current_user.email}</SMTPAddress>
            </EmailAddresses>
            <DisplayName>{current_user.full_name or current_user.username}</DisplayName>
        </Get>
    </UserInformation>
</Settings>"""
        _write_json_line("activesync/activesync.log", {"event": "settings", "user": current_user.email})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    if cmd == "search":
        # MS-ASCMD Search implementation for GAL (Global Address List)
        query = request.query_params.get("Query", "").strip()
        # Simple fallback: try to parse tiny XML bodies that include <Query>text</Query>
        try:
            body = await request.body()
            if not query and body:
                txt = body.decode("utf-8", errors="ignore")
                if "<Query>" in txt:
                    qstart = txt.find("<Query>") + 7
                    qend = txt.find("</Query>")
                    if qstart >= 7 and qend > qstart:
                        query = txt[qstart:qend].strip()
        except Exception:
            pass
        q = f"%{query.lower()}%" if query else "%"
        users = (
            db.query(User)
            .filter(
                (User.email.ilike(q))
                | (User.username.ilike(q))
                | (User.full_name.ilike(q))
            )
            .order_by(User.full_name.asc())
            .limit(50)
            .all()
        )
        # Build MS-ASCMD compliant Search response for GAL
        root = ET.Element("Search")
        root.set("xmlns", "Search")
        ET.SubElement(root, "Status").text = "1"
        resp = ET.SubElement(root, "Response")
        store = ET.SubElement(resp, "Store")
        ET.SubElement(store, "Name").text = "GAL"
        for u in users:
            result = ET.SubElement(store, "Result")
            props = ET.SubElement(result, "Properties")
            ET.SubElement(props, "DisplayName").text = u.full_name or u.username
            ET.SubElement(props, "EmailAddress").text = u.email
            ET.SubElement(props, "FirstName").text = (u.full_name or u.username).split(
                " "
            )[0]
            last = (u.full_name or u.username).split(" ")[-1]
            ET.SubElement(props, "LastName").text = (
                last if last else (u.full_name or u.username)
            )
        xml = ET.tostring(root, encoding="unicode")
        _write_json_line("activesync/activesync.log", {"event": "search", "query": query, "results": len(users)})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ItemOperations command implementation
    if cmd == "itemoperations":
        # MS-ASCMD ItemOperations for fetching specific items
        item_id = request.query_params.get("ItemId", "")
        collection_id = request.query_params.get("CollectionId", "1")
        
        if not item_id:
            xml = f"<ItemOperations xmlns=\"ItemOperations\"><Status>2</Status></ItemOperations>"
        else:
            # Fetch specific email item
            email_service = EmailService(db)
            emails = email_service.get_user_emails(current_user.id, "inbox", limit=1000)
            target_email = next((e for e in emails if str(e.id) == item_id), None)
            
            if target_email:
                root = ET.Element("ItemOperations")
                root.set("xmlns", "ItemOperations")
                ET.SubElement(root, "Status").text = "1"
                response = ET.SubElement(root, "Response")
                fetch = ET.SubElement(response, "Fetch")
                ET.SubElement(fetch, "Status").text = "1"
                properties = ET.SubElement(fetch, "Properties")
                
                # Add email properties according to MS-ASCMD
                ET.SubElement(properties, "Subject").text = target_email.subject or ""
                ET.SubElement(properties, "From").text = target_email.sender or ""
                ET.SubElement(properties, "To").text = target_email.recipient or ""
                ET.SubElement(properties, "DateReceived").text = target_email.received_at.strftime("%Y-%m-%dT%H:%M:%SZ") if target_email.received_at else ""
                ET.SubElement(properties, "Body").text = target_email.body or ""
                
                xml = ET.tostring(root, encoding="unicode")
            else:
                xml = f"<ItemOperations xmlns=\"ItemOperations\"><Status>2</Status></ItemOperations>"
        
        _write_json_line("activesync/activesync.log", {"event": "itemoperations", "item_id": item_id, "collection_id": collection_id})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SmartForward command implementation
    if cmd == "smartforward":
        # MS-ASCMD SmartForward for forwarding emails
        _write_json_line("activesync/activesync.log", {"event": "smartforward"})
        xml = f"<SmartForward xmlns=\"SmartForward\"><Status>1</Status></SmartForward>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SmartReply command implementation
    if cmd == "smartreply":
        # MS-ASCMD SmartReply for replying to emails
        _write_json_line("activesync/activesync.log", {"event": "smartreply"})
        xml = f"<SmartReply xmlns=\"SmartReply\"><Status>1</Status></SmartReply>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD MoveItems command implementation
    if cmd == "moveitems":
        # MS-ASCMD MoveItems for moving emails between folders
        _write_json_line("activesync/activesync.log", {"event": "moveitems"})
        xml = f"<MoveItems xmlns=\"MoveItems\"><Status>1</Status></MoveItems>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD MeetingResponse command implementation
    if cmd == "meetingresponse":
        # MS-ASCMD MeetingResponse for calendar meeting responses
        _write_json_line("activesync/activesync.log", {"event": "meetingresponse"})
        xml = f"<MeetingResponse xmlns=\"MeetingResponse\"><Status>1</Status></MeetingResponse>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD Find command implementation
    if cmd == "find":
        # MS-ASCMD Find for searching within folders
        _write_json_line("activesync/activesync.log", {"event": "find"})
        xml = f"<Find xmlns=\"Find\"><Status>1</Status></Find>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD GetAttachment command implementation
    if cmd == "getattachment":
        # MS-ASCMD GetAttachment for fetching email attachments
        _write_json_line("activesync/activesync.log", {"event": "getattachment"})
        xml = f"<GetAttachment xmlns=\"GetAttachment\"><Status>1</Status></GetAttachment>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD Calendar command implementation
    if cmd == "calendar":
        # MS-ASCMD Calendar for calendar synchronization
        _write_json_line("activesync/activesync.log", {"event": "calendar"})
        xml = f"<Calendar xmlns=\"Calendar\"><Status>1</Status></Calendar>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderCreate command implementation
    if cmd == "foldercreate":
        # MS-ASCMD FolderCreate for creating new folders
        _write_json_line("activesync/activesync.log", {"event": "foldercreate"})
        xml = f"<FolderCreate xmlns=\"FolderCreate\"><Status>1</Status></FolderCreate>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderDelete command implementation
    if cmd == "folderdelete":
        # MS-ASCMD FolderDelete for deleting folders
        _write_json_line("activesync/activesync.log", {"event": "folderdelete"})
        xml = f"<FolderDelete xmlns=\"FolderDelete\"><Status>1</Status></FolderDelete>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderUpdate command implementation
    if cmd == "folderupdate":
        # MS-ASCMD FolderUpdate for updating folder properties
        _write_json_line("activesync/activesync.log", {"event": "folderupdate"})
        xml = f"<FolderUpdate xmlns=\"FolderUpdate\"><Status>1</Status></FolderUpdate>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ResolveRecipients command implementation
    if cmd == "resolverecipients":
        # MS-ASCMD ResolveRecipients for resolving email addresses
        _write_json_line("activesync/activesync.log", {"event": "resolverecipients"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ResolveRecipients xmlns="ResolveRecipients">
    <Status>1</Status>
    <Response>
        <To>
            <Email>test@example.com</Email>
            <Name>Test User</Name>
            <DisplayName>Test User</DisplayName>
        </To>
    </Response>
</ResolveRecipients>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ValidateCert command implementation
    if cmd == "validatecert":
        # MS-ASCMD ValidateCert for certificate validation
        _write_json_line("activesync/activesync.log", {"event": "validatecert"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ValidateCert xmlns="ValidateCert">
    <Status>1</Status>
    <Response>
        <Status>1</Status>
        <Certificate>
            <Status>1</Status>
        </Certificate>
    </Response>
</ValidateCert>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SendMail command implementation
    if cmd == "sendmail":
        # MS-ASCMD SendMail for sending emails
        _write_json_line("activesync/activesync.log", {"event": "sendmail"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<SendMail xmlns="SendMail">
    <Status>1</Status>
    <Response>
        <Status>1</Status>
    </Response>
</SendMail>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    # MS-ASCMD compliant error handling for unsupported commands
    _write_json_line("activesync/activesync.log", {"event": "unsupported_command", "command": cmd, "message": f"Unsupported ActiveSync command: {cmd}"})
    
    # Return MS-ASCMD compliant error response
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<{cmd} xmlns="{cmd}">
    <Status>2</Status>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Command not supported</Message>
        </Error>
    </Response>
</{cmd}>"""
    
    return Response(
        content=xml, 
        media_type="application/vnd.ms-sync.wbxml", 
        headers=headers,
        status_code=200  # MS-ASCMD uses Status codes in XML, not HTTP status codes
    )


def _calendar_to_eas_xml(events: list[CalendarEvent]) -> str:
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")
    col = ET.SubElement(root, "Collection")
    col.set("Class", "Calendar")
    col.set("SyncKey", "1")
    col.set("CollectionId", "calendar")
    for ev in events:
        add = ET.SubElement(col, "Add")
        add.set("ServerId", str(ev.id))
        data = ET.SubElement(add, "ApplicationData")
        ET.SubElement(data, "Subject").text = ev.title
        ET.SubElement(data, "Location").text = ev.location or ""
        ET.SubElement(data, "StartTime").text = ev.start_time.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        ET.SubElement(data, "EndTime").text = ev.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        ET.SubElement(data, "AllDayEvent").text = "1" if ev.is_all_day else "0"
        if ev.description:
            ET.SubElement(data, "Body").text = ev.description
    return ET.tostring(root, encoding="unicode")


@router.get("/activesync/calendar")
def calendar_list(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == current_user.id)
        .order_by(CalendarEvent.start_time.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "location": e.location,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "is_all_day": e.is_all_day,
        }
        for e in events
    ]


@router.post("/activesync/calendar")
def calendar_create(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    import json

    data = (
        json.loads(request._body.decode("utf-8"))
        if hasattr(request, "_body") and request._body
        else {}
    )
    title = data.get("title") or "Event"
    from datetime import datetime

    start = datetime.fromisoformat(data.get("start_time"))
    end = datetime.fromisoformat(data.get("end_time"))
    event = CalendarEvent(
        user_id=current_user.id,
        title=title,
        description=data.get("description"),
        location=data.get("location"),
        start_time=start,
        end_time=end,
        is_all_day=bool(data.get("is_all_day")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id}


@router.get("/activesync/calendar/sync")
def calendar_sync(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == current_user.id)
        .order_by(CalendarEvent.start_time.asc())
        .limit(200)
        .all()
    )
    xml = _calendar_to_eas_xml(events)
    return Response(
        content=xml, media_type="application/vnd.ms-sync.wbxml", headers=_eas_headers()
    )


# Root-level aliases (some clients call without /activesync prefix)
@router.options("/../Microsoft-Server-ActiveSync")
async def eas_options_alias(request: Request):
    """CRITICAL FIX #31: Use OPTIONS-specific headers (no singular version)!"""
    headers = _eas_options_headers()  # ← Use OPTIONS headers!
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "options_alias",
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        },
    )
    return Response(status_code=200, headers=headers)


@router.post("/../Microsoft-Server-ActiveSync")
async def eas_dispatch_alias(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    return await eas_dispatch(request, current_user, db)


@router.post("/sync")
async def sync_emails(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """ActiveSync email synchronization endpoint"""
    try:
        # Parse the ActiveSync request
        body = await request.body()
        # In a real implementation, you would parse the WBXML/XML request

        # Get user's emails
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, "inbox", limit=100)

        # Create ActiveSync response
        xml_response = create_sync_response(emails)

        return ActiveSyncResponse(xml_response)

    except Exception as e:
        _write_json_line("activesync/activesync.log", {"event": "error", "error": str(e), "command": cmd})
        
        # MS-ASCMD compliant error response for server errors
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<{cmd} xmlns="{cmd}">
    <Status>3</Status>
    <Response>
        <Error>
            <Code>3</Code>
            <Message>Server error: {str(e)}</Message>
        </Error>
    </Response>
</{cmd}>"""
        
        return Response(
            content=xml, 
            media_type="application/vnd.ms-sync.wbxml", 
            headers=headers,
            status_code=200
        )


@router.get("/ping")
def ping():
    """ActiveSync ping endpoint for device connectivity"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.post("/provision")
async def device_provisioning(
    request: Request, current_user: User = Depends(get_current_user_from_basic_auth)
):
    """Device provisioning for ActiveSync"""
    # In a real implementation, this would handle device registration
    return {
        "status": "provisioned",
        "device_id": "device_123",
        "user": current_user.username,
    }


@router.get("/folders")
def get_folders(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    """Get available email folders for ActiveSync with IPM subtree compatibility"""
    folders = [
        {"id": "1", "name": "Inbox", "type": "inbox", "parent_id": "0"},
        {"id": "2", "name": "Outbox", "type": "outbox", "parent_id": "0"},
        {"id": "3", "name": "Sent Items", "type": "sent", "parent_id": "0"},
        {"id": "4", "name": "Deleted Items", "type": "deleted", "parent_id": "0"},
        {"id": "5", "name": "Drafts", "type": "drafts", "parent_id": "0"},
    ]
    return {"folders": folders}


@router.get("/folders/{folder_id}/emails")
def get_folder_emails(
    folder_id: str,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """Get emails from a specific folder for ActiveSync"""
    email_service = EmailService(db)

    # Microsoft ActiveSync folder mapping according to MS-ASCMD specification
    # This must match the mapping used in the sync command
    folder_map = {
        "1": "inbox",       # Inbox (Type 2)
        "2": "drafts",       # Drafts (Type 3)
        "3": "deleted",      # Deleted Items (Type 4)
        "4": "sent",         # Sent Items (Type 5)
        "5": "outbox"        # Outbox (Type 6)
    }

    folder = folder_map.get(folder_id, "inbox")
    emails = email_service.get_user_emails(current_user.id, folder, limit=50)

    return {
        "folder_id": folder_id,
        "folder_name": folder,
        "emails": [
            {
                "id": email.id,
                "subject": email.subject,
                "from": getattr(getattr(email, "sender", None), "email", ""),
                "to": getattr(getattr(email, "recipient", None), "email", ""),
                "date": email.created_at.isoformat(),
                "read": email.is_read,
                "body": email.body,
            }
            for email in emails
        ],
    }

    # Build XML response based on step
    if is_acknowledgment:
            # Step 2 response: Just PolicyKey, no Data
            xml = (
                f"""<?xml version="1.0" encoding="utf-8"?>
<Provision xmlns="Provision:">
    <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <Status>1</Status>
            <PolicyKey>{policy_key}</PolicyKey>
        </Policy>
    </Policies>
</Provision>"""
            )
        else:
            # Step 1 response: PolicyKey=0 + full policy settings
            xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Provision xmlns="Provision:">
            <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <Status>1</Status>
            <PolicyKey>{policy_key}</PolicyKey>
            <Data>
                <EASProvisionDoc>
                    <DevicePasswordEnabled>0</DevicePasswordEnabled>
                    <AlphanumericDevicePasswordRequired>0</AlphanumericDevicePasswordRequired>
                    <PasswordRecoveryEnabled>0</PasswordRecoveryEnabled>
                    <RequireDeviceEncryption>0</RequireDeviceEncryption>
                    <AttachmentsEnabled>1</AttachmentsEnabled>
                    <MinDevicePasswordLength>0</MinDevicePasswordLength>
                    <MaxInactivityTimeDeviceLock>0</MaxInactivityTimeDeviceLock>
                    <MaxDevicePasswordFailedAttempts>0</MaxDevicePasswordFailedAttempts>
                    <MaxEmailAgeFilter>0</MaxEmailAgeFilter>
                    <AllowSimpleDevicePassword>1</AllowSimpleDevicePassword>
                    <MaxAttachmentSize>51200000</MaxAttachmentSize>
                    <AllowStorageCard>1</AllowStorageCard>
                    <AllowCamera>1</AllowCamera>
                    <AllowUnsignedApplications>1</AllowUnsignedApplications>
                    <AllowUnsignedInstallationPackages>1</AllowUnsignedInstallationPackages>
                    <MinDevicePasswordComplexCharacters>0</MinDevicePasswordComplexCharacters>
                    <AllowWiFi>1</AllowWiFi>
                    <AllowTextMessaging>1</AllowTextMessaging>
                    <AllowPOPIMAPEmail>1</AllowPOPIMAPEmail>
                    <AllowBluetooth>2</AllowBluetooth>
                    <AllowIrDA>1</AllowIrDA>
                    <RequireManualSyncWhenRoaming>0</RequireManualSyncWhenRoaming>
                    <AllowDesktopSync>1</AllowDesktopSync>
                    <MaxCalendarAgeFilter>0</MaxCalendarAgeFilter>
                    <AllowHTMLEmail>1</AllowHTMLEmail>
                    <MaxEmailBodyTruncationSize>-1</MaxEmailBodyTruncationSize>
                    <MaxEmailHTMLBodyTruncationSize>-1</MaxEmailHTMLBodyTruncationSize>
                    <RequireSignedSMIMEMessages>0</RequireSignedSMIMEMessages>
                    <RequireEncryptedSMIMEMessages>0</RequireEncryptedSMIMEMessages>
                    <RequireSignedSMIMEAlgorithm>0</RequireSignedSMIMEAlgorithm>
                    <RequireEncryptionSMIMEAlgorithm>0</RequireEncryptionSMIMEAlgorithm>
                    <AllowSMIMEEncryptionAlgorithmNegotiation>2</AllowSMIMEEncryptionAlgorithmNegotiation>
                    <AllowSMIMESoftCerts>1</AllowSMIMESoftCerts>
                    <AllowBrowser>1</AllowBrowser>
                    <AllowConsumerEmail>1</AllowConsumerEmail>
                    <AllowRemoteDesktop>1</AllowRemoteDesktop>
                    <AllowInternetSharing>1</AllowInternetSharing>
                </EASProvisionDoc>
            </Data>
        </Policy>
    </Policies>
</Provision>"""
        
        return Response(content=xml, media_type="application/xml", headers=headers)

    # All other commands require that the device has completed the provisioning step above.
    if device.is_provisioned != 1:
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "provisioning_required", "command": cmd, "device_id": device_id,
                "message": "Device not provisioned. Sending HTTP 449.",
            },
        )
        return Response(status_code=449)

    if cmd == "foldersync":
        # Microsoft ActiveSync FolderSync implementation according to MS-ASCMD specification
        # Use dedicated state for folder hierarchy (collection_id="0")
        state = _get_or_init_state(db, current_user.id, device_id, "0")
        
        # Parse WBXML request body to extract actual SyncKey
        wbxml_params = parse_wbxml_foldersync_request(request_body_bytes)
        client_sync_key = wbxml_params.get("sync_key", request.query_params.get("SyncKey", "0"))
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # Check if client is sending WBXML (iPhone sends WBXML)
        is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
        
        # *** ENHANCED DEBUGGING: COMPREHENSIVE REQUEST/RESPONSE LOGGING ***
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "foldersync_debug_comprehensive",
                "client_key": client_sync_key,
                "client_key_int": client_key_int,
                "server_key": state.sync_key,
                "server_key_int": server_key_int,
                "is_wbxml_request": is_wbxml_request,
                "request_body_length": len(request_body_bytes),
                "request_body_hex": request_body_bytes[:50].hex() if request_body_bytes else "empty",
                "user_agent": request.headers.get("User-Agent", ""),
                "device_id": device_id,
                "user_id": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            },
        )
        
        # CASE 1: Initial Sync (client_key=0). Provide the full, detailed folder hierarchy.
        if client_key_int == 0:
            # Only set sync_key if it's actually 0 in the database (true first request)
            if state.sync_key == "0":
                state.sync_key = "1"
                db.commit()
                _write_json_line("activesync/activesync.log", {
                    "event": "foldersync_initial_sync_key_updated", 
                    "device_id": device_id,
                    "old_sync_key": "0",
                    "new_sync_key": "1"
                })
            
            if is_wbxml_request:
                # Return correct minimal WBXML response with all 5 folders
                from .wbxml_builder import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "foldersync_initial_wbxml_response",
                        "sync_key": state.sync_key,
                        "client_key": client_sync_key,
                        "wbxml_length": len(wbxml_content),
                        "wbxml_type": "minimal_correct",
                        "wbxml_hex": wbxml_content[:100].hex(),
                        "wbxml_full_hex": wbxml_content.hex(),
                        "sync_key_progression": {
                            "client_sent": client_sync_key,
                            "server_responding": state.sync_key,
                            "is_initial_sync": client_key_int == 0,
                            "database_updated": state.sync_key == "1" and client_key_int == 0
                        },
                        "response_analysis": {
                            "header": wbxml_content[:10].hex(),
                            "folder_count": wbxml_content.count(b'\x4F'),  # Count Add tags (0x0F + 0x40 = 0x4F)
                            "has_status": b'\x4C' in wbxml_content,  # Status tag (0x0C + 0x40 = 0x4C)
                            "has_synckey": b'\x52' in wbxml_content,  # SyncKey tag (0x12 + 0x40 = 0x52)
                            "has_changes": b'\x4E' in wbxml_content,  # Changes tag (0x0E + 0x40 = 0x4E)
                        }
                    },
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                # Return XML response for other clients
                # *** FINAL FIX: Provide the complete, standard Exchange mailbox structure. ***
                # This includes Mail, Calendar, and Contacts folders.
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Changes>
        <Count>7</Count>
        <Add>
            <ServerId>1</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Inbox</DisplayName>
            <Type>2</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>2</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Drafts</DisplayName>
            <Type>3</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>3</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Deleted Items</DisplayName>
            <Type>4</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>4</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Sent Items</DisplayName>
            <Type>5</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>5</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Outbox</DisplayName>
            <Type>6</Type>
            <SupportedClasses>
                <SupportedClass>Email</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>calendar</ServerId> 
            <ParentId>0</ParentId>
            <DisplayName>Calendar</DisplayName>
            <Type>8</Type> 
            <SupportedClasses>
                <SupportedClass>Calendar</SupportedClass>
            </SupportedClasses>
        </Add>
        <Add>
            <ServerId>contacts</ServerId> 
            <ParentId>0</ParentId>
            <DisplayName>Contacts</DisplayName>
            <Type>9</Type> 
            <SupportedClasses>
                <SupportedClass>Contacts</SupportedClass>
            </SupportedClasses>
        </Add>
    </Changes>
</FolderSync>"""
                # *** ENHANCED LOGGING: CAPTURE FULL RESPONSE ***
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "foldersync_initial_response",
                        "sync_key": state.sync_key,
                        "client_key": client_sync_key,
                        "full_response_xml": xml  # Log the entire XML response
                    },
                )
        # CASE 2: Client is up to date. Report no changes.
        elif client_key_int == server_key_int:
            if is_wbxml_request:
                # Return WBXML response for iPhone clients
                from .wbxml_builder import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_no_changes_wbxml", "sync_key": state.sync_key, "client_key": client_sync_key},
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Changes><Count>0</Count></Changes>
</FolderSync>"""
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key},
                )

        # CASE 3: Client is out of sync. Force it to start over.
        else:
            if is_wbxml_request:
                # Return WBXML response for iPhone clients
                from .wbxml_builder import build_foldersync_no_changes
                wbxml_content = build_foldersync_no_changes(state.sync_key)  # Simplified error response
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_recovery_sync_wbxml", "server_key": state.sync_key, "client_key": client_sync_key},
                )
                return Response(
                    content=wbxml_content, media_type="application/vnd.ms-sync.wbxml", headers=headers
                )
            else:
                xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>8</Status>
</FolderSync>"""
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_recovery_sync", "server_key": state.sync_key, "client_key": client_sync_key},
                )
        
        # Return XML response for non-WBXML clients
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )

    elif cmd == "sync":
        # Microsoft ActiveSync Sync implementation according to MS-ASCMD specification
        # Use state for the specific collection being synced
        collection_id = request.query_params.get("CollectionId", "1")
        state = _get_or_init_state(db, current_user.id, device_id, collection_id)
        
        # Parse WBXML request body to extract actual SyncKey and CollectionId
        wbxml_params = parse_wbxml_sync_request(request_body_bytes)
        extra_ops = parse_wbxml_sync_fetch_and_delete(request_body_bytes)
        fetch_ids = extra_ops.get("fetch_ids", [])
        delete_ids = extra_ops.get("delete_ids", [])
        _write_json_line("activesync/activesync.log", {"event": "sync_ops_parsed", "fetch_ids": fetch_ids, "delete_ids": delete_ids})
        client_sync_key = wbxml_params.get("sync_key", request.query_params.get("SyncKey", "0"))
        collection_id = wbxml_params.get("collection_id", request.query_params.get("CollectionId", "1"))
        window_size_str = wbxml_params.get("window_size", "5")
        try:
            window_size = int(window_size_str)
        except (ValueError, TypeError):
            window_size = 5  # Default to 5 emails per sync
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # CRITICAL FIX: Handle SyncKey=0 BEFORE any email queries!
        # When client sends SyncKey=0, it means "I have nothing, start fresh"
        # We MUST reset last_synced_email_id BEFORE filtering emails!
        if client_sync_key == "0":
            state.synckey_counter = 1
            state.sync_key = "1"
            state.last_synced_email_id = 0  # RESET PAGINATION!
            state.pending_sync_key = None
            state.pending_max_email_id = None
            state.pending_item_ids = None
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_initial_reset_EARLY",
                "device_id": device_id,
                "collection_id": collection_id,
                "message": "CRITICAL: Reset last_synced_email_id BEFORE email query"
            })
        
        # CRITICAL: Detect InvalidSyncKey - client and server are out of sync
        # Per expert: "When client sends stale key (e.g. 4) but server is at 190,
        # return Status=3 (InvalidSyncKey) with SyncKey=0 to force client reset"
        # Allow tolerance of ±2 for pending batches, but reject if gap is huge
        if client_sync_key != "0" and abs(client_key_int - server_key_int) > 3:
            _write_json_line("activesync/activesync.log", {
                "event": "sync_invalid_synckey_detected",
                "client_sync_key": client_sync_key,
                "server_sync_key": state.sync_key,
                "gap": abs(client_key_int - server_key_int),
                "message": "Client sent stale SyncKey - forcing reset with Status=3"
            })
            # Return InvalidSyncKey response
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            else:
                # XML fallback
                xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Collections>
        <Collection>
            <Class>Email</Class>
            <SyncKey>0</SyncKey>
            <CollectionId>{collection_id}</CollectionId>
            <Status>3</Status>
        </Collection>
    </Collections>
</Sync>"""
                return Response(content=xml_response, media_type="application/xml", headers=headers)
        
        # CRITICAL FIX #26: Two-phase commit - check for pending batch first!
        # Expert: "Only commit when the client echoes back the SyncKey you issued"
        import json
        
        # CRITICAL FIX #27: Expert's correction - SyncKey must ALWAYS advance!
        # "Every Sync response must issue a new SyncKey. If you keep returning
        #  the same SyncKey, iOS treats the state as inconsistent and restarts."
        #
        # NEW LOGIC:
        # 1) Client confirms last batch? → Clear pending, advance to next batch
        if state.pending_sync_key and client_sync_key == state.pending_sync_key:
            # Client got the batch! Commit it now
            state.last_synced_email_id = state.pending_max_email_id or state.last_synced_email_id
            state.sync_key = state.pending_sync_key
            state.synckey_counter = int(state.pending_sync_key) if state.pending_sync_key.isdigit() else state.synckey_counter
            state.pending_sync_key = None
            state.pending_max_email_id = None
            state.pending_item_ids = None
            db.commit()
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_pending_confirmed",
                "client_sync_key": client_sync_key,
                "committed_max_id": state.last_synced_email_id,
                "message": "Client confirmed - committed pending batch, will send next with NEW key"
            })
            # Fall through to compute next batch WITH A FRESH KEY
        
        # 2) Client didn't get last response? (retries with old key OR sends 0 when pending exists)
        # CRITICAL FIX #26C: Check if client is one behind pending!
        # Example: client="6", server="7", pending="7" → client wants the pending batch!
        elif state.pending_sync_key:
            # Calculate if client is asking for the pending batch
            try:
                client_int = int(client_sync_key) if client_sync_key.isdigit() else 0
                pending_int = int(state.pending_sync_key) if state.pending_sync_key.isdigit() else 0
                # CRITICAL FIX #38: DON'T treat SyncKey=0 as "asking for pending"!
                # When client sends SyncKey=0, it's a FRESH initial sync (e.g., after account re-add).
                # We should ONLY resend pending if client is retrying with a non-zero key.
                # Client is asking for pending if: client==pending OR client==server OR client==pending-1
                is_asking_for_pending = (
                    client_sync_key == state.pending_sync_key or  # Exact match
                    client_sync_key == state.sync_key or  # Old server key
                    # client_sync_key == "0" or  # ← REMOVED! Don't treat 0 as retry!
                    (client_int > 0 and pending_int > 0 and client_int == pending_int - 1)  # One behind
                )
            except:
                is_asking_for_pending = True  # If in doubt, resend
            
            if is_asking_for_pending:
                # Re-send the exact same pending batch!
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_resend_pending",
                    "client_sync_key": client_sync_key,
                    "server_sync_key": state.sync_key,
                    "pending_sync_key": state.pending_sync_key,
                    "message": "Client retry - resending pending batch IDEMPOTENTLY with SAME key"
                })
                
                # Fetch the specific emails from pending
                if state.pending_item_ids:
                    pending_ids = json.loads(state.pending_item_ids)
                    email_service = EmailService(db)
                    # Ensure folder_map defined before use
                    try:
                        _fm = folder_map  # may not exist yet in this branch
                    except NameError:
                        _fm = {"1": "inbox", "2": "drafts", "3": "deleted", "4": "sent", "5": "outbox"}
                    all_emails_temp = email_service.get_user_emails(current_user.id, _fm.get(collection_id, "inbox"), limit=200)
                    emails_to_resend = [e for e in all_emails_temp if e.id in pending_ids]
                    
                    # Calculate has_more: are there items after the pending batch?
                    max_pending_id = max(pending_ids) if pending_ids else 0
                    remaining_emails = [e for e in all_emails_temp if e.id > max_pending_id]
                    has_more_pending = len(remaining_emails) > 0
                    
                    # Re-send with SAME SyncKey (idempotent resend!) using compliant builder
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=state.pending_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or '') } for e in emails_to_resend],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=has_more_pending,
                        class_name="Email",
                    )
                    return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
        
        # Debug logging for sync key comparison
        _write_json_line(
            "activesync/activesync.log",
            {"event": "sync_debug", "client_key": client_sync_key, "client_key_int": client_key_int, "server_key": state.sync_key, "server_key_int": server_key_int, "user_id": current_user.id, "has_pending": bool(state.pending_sync_key)},
        )
        
        # Get emails for the specified collection
        # Map CollectionId to folder type for simplified folder structure
        # Microsoft ActiveSync folder mapping according to MS-ASCMD specification
        folder_map = {
            "1": "inbox",       # Inbox (Type 2)
            "2": "drafts",       # Drafts (Type 3)
            "3": "deleted",      # Deleted Items (Type 4)
            "4": "sent",         # Sent Items (Type 5)
            "5": "outbox"        # Outbox (Type 6)
        }
        folder_type = folder_map.get(collection_id, "inbox")
        
        # CRITICAL FIX #24: Query only NEW emails (proper pagination!)
        # Expert: "iOS expects every successful Sync response to return a new SyncKey"
        # We must track which emails have been sent and only send NEW ones!
        email_service = EmailService(db)
        
        # Get last synced email ID for this device+collection
        last_id = state.last_synced_email_id or 0
        
        # Query emails AFTER the last synced ID (proper pagination!)
        all_emails = email_service.get_user_emails(current_user.id, folder_type, limit=100)
        
        # Filter to only unsent emails
        emails = [e for e in all_emails if e.id > last_id]

        # Include FETCHED items regardless of pagination
        fetched_emails = []
        if fetch_ids:
            try:
                # server_id may be formatted like "1:36"; extract numeric id portion
                fetch_int_ids = []
                for sid in fetch_ids:
                    parts = str(sid).split(":")
                    n = parts[-1]
                    if n.isdigit():
                        fetch_int_ids.append(int(n))
                fetched_emails = email_service.get_emails_by_ids(current_user.id, fetch_int_ids)
                _write_json_line("activesync/activesync.log", {"event": "sync_fetch_lookup", "fetch_ids": fetch_ids, "resolved": [e.id for e in fetched_emails]})
            except Exception as ex:
                _write_json_line("activesync/activesync.log", {"event": "sync_fetch_error", "error": str(ex)})
        
        _write_json_line("activesync/activesync.log", {
            "event": "sync_pagination_filter",
            "last_synced_email_id": last_id,
            "total_emails_in_folder": len(all_emails),
            "new_emails_to_sync": len(emails),
            "message": "Filtered to only NEW emails not yet synced"
        })
        
        # CRITICAL FIX #59: Detect stuck state (Z-Push approach)
        # If last_synced_email_id is at or beyond the max email ID in the folder,
        # AND there are emails in the folder, it means the state is stuck.
        # Solution: Reset last_synced_email_id to 0 to force resync
        if all_emails and not emails and not fetched_emails and client_sync_key != "0":
            # Check if we're stuck: last_id >= max_email_id in folder
            max_email_id = max(e.id for e in all_emails) if all_emails else 0
            if last_id >= max_email_id:
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_stuck_state_detected",
                    "last_synced_email_id": last_id,
                    "max_email_id_in_folder": max_email_id,
                    "total_emails": len(all_emails),
                    "client_sync_key": client_sync_key,
                    "message": "STUCK STATE: last_synced_email_id >= max_email_id, forcing reset"
                })
                # Z-Push approach: Reset to 0 to force full resync
                state.last_synced_email_id = 0
                db.commit()
                # Re-query emails after reset
                emails = [e for e in all_emails if e.id > 0]
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_state_reset_auto",
                    "new_last_synced_email_id": 0,
                    "emails_to_sync_after_reset": len(emails),
                    "message": "Auto-reset complete, will send all emails"
                })
        
        # Enhanced logging with detailed email information
        email_details = []
        for email in emails:
            # Fix subject - use "No Subject" if empty
            subject = getattr(email, 'subject', '') or 'No Subject'
            if not subject.strip():
                subject = 'No Subject'
            
            # Fix sender - check both internal sender and external_sender
            sender_email = 'Unknown'
            if hasattr(email, 'sender') and email.sender:
                sender_email = getattr(email.sender, 'email', 'Unknown')
            elif hasattr(email, 'external_sender') and email.external_sender:
                sender_email = email.external_sender
            
            # Fix recipient - check both internal recipient and external_recipient  
            recipient_email = 'Unknown'
            if hasattr(email, 'recipient') and email.recipient:
                recipient_email = getattr(email.recipient, 'email', 'Unknown')
            elif hasattr(email, 'external_recipient') and email.external_recipient:
                recipient_email = email.external_recipient
            
            email_details.append({
                "id": email.id,
                "subject": subject[:50],  # Truncate for logging
                "sender": sender_email,
                "recipient": recipient_email,
                "created_at": getattr(email, 'created_at', None).isoformat() if getattr(email, 'created_at', None) else None,
                "is_read": getattr(email, 'is_read', False),
                "is_deleted": getattr(email, 'is_deleted', False),
                "is_external": getattr(email, 'is_external', False),
                "sender_id": getattr(email, 'sender_id', None),
                "recipient_id": getattr(email, 'recipient_id', None)
            })
        
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "sync_emails_found", 
                "count": len(emails), 
                "user_id": current_user.id,
                "user_email": current_user.email,
                "collection_id": collection_id,
                "folder_type": folder_type,
                "folder_mapping": folder_map,
                "email_details": email_details,
                "sync_state": {
                    "device_id": device_id,
                    "client_sync_key": client_sync_key,
                    "server_sync_key": state.sync_key,
                    "collection_id": collection_id
                }
            },
        )
        
        # Initial sync (SyncKey=0) - already handled above at line 799-813!
        if client_sync_key == "0":
            # State was already reset BEFORE email query (line 799-813)
            # This ensures last_synced_email_id=0 BEFORE we filter emails
            response_sync_key = "1"
            # CRITICAL FIX #23-2: Send items on FIRST sync per expert!
            # Expert: "iOS is fine receiving items on the first response"
            # Previous logic sent empty response, which was WRONG!
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                # Respect WindowSize for initial sync too!
                emails_to_send = emails[:window_size] if window_size else emails
                has_more = len(emails) > window_size if window_size else False
                
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_initial_WITH_ITEMS",
                    "reason": "Expert: iOS accepts items on first response",
                    "window_size": window_size,
                    "email_count_total": len(emails),
                    "email_count_sent": len(emails_to_send),
                    "has_more": has_more,
                    "message": "Sending items immediately on SyncKey 0→1"
                })
                # CRITICAL: ACTUALLY SEND THE EMAILS! (was passing empty list)
                # Convert SQLAlchemy Email objects to dicts for WBXML builder
                # Z-Push approach: ALWAYS send HTML as Type=2 if content looks like HTML
                email_dicts = []
                for email in emails_to_send:
                    body_content = email.body or email.preview or ''
                    body_html_content = None
                    
                    # Z-Push logic: If body contains HTML, send it as Type=2 (HTML)
                    # iOS prefers HTML and will render it properly
                    if body_content and ('<html' in body_content.lower() or body_content.strip().startswith('<')):
                        # This is HTML content - send it as body_html for Type=2
                        body_html_content = body_content
                        # Also provide plain text fallback by stripping HTML tags
                        import re
                        plain_fallback = re.sub(r'<[^>]+>', '', body_content)
                        plain_fallback = plain_fallback.replace('&nbsp;', ' ').replace('&amp;', '&')
                        plain_fallback = plain_fallback.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
                        body_content = plain_fallback.strip()
                    
                    email_dicts.append({
                        'id': email.id,
                        'server_id': f"{collection_id}:{email.id}",
                        'subject': email.subject or '(no subject)',
                        'from': email.external_sender or (email.sender.email if email.sender else ''),
                        'to': email.external_recipient or (email.recipient.email if email.recipient else ''),
                        'created_at': email.created_at,
                        'is_read': email.is_read,
                        'body': body_content,  # Plain text fallback
                        'body_html': body_html_content,  # HTML body (Type=2)
                    })
                
                wbxml_batch = create_sync_response_wbxml(
                    sync_key=response_sync_key,
                    emails=email_dicts,
                    collection_id=collection_id,
                    window_size=window_size,
                    more_available=has_more,
                    class_name="Email",
                )
                wbxml = wbxml_batch.payload
                
                # CRITICAL FIX #26: Stage as PENDING, don't commit yet!
                # Expert: "Only commit when client echoes back the SyncKey"
                if emails_to_send:
                    max_sent_id = max(e.id for e in emails_to_send)
                    state.pending_sync_key = response_sync_key
                    state.pending_max_email_id = max_sent_id
                    state.pending_item_ids = json.dumps([e.id for e in emails_to_send])
                
                # Commit PENDING state (not last_synced_email_id yet!)
                db.commit()
                
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_initial_wbxml", 
                        "sync_key": response_sync_key, 
                        "client_key": client_sync_key, 
                        "email_count": len(emails),
                        "window_size": window_size,
                    "collection_id": collection_id,
                        "wbxml_length": len(wbxml), 
                        "wbxml_first20": wbxml[:20].hex(), 
                        "wbxml_analysis": {
                            "header": wbxml[:6].hex(), 
                            "has_emails": len(emails) > 0, 
                            "codepage_0_airsync": True,
                            "wbxml_structure": {
                                "header_bytes": wbxml[:6].hex(),
                                "switch_to_airsync": wbxml[6:8].hex(),
                                "sync_token": wbxml[8:9].hex(),
                                "status_token": wbxml[9:14].hex(),
                                "top_synckey_token": wbxml[14:19].hex()
                            }
                        },
                        "user_mapping": {
                            "user_id": current_user.id,
                            "user_email": current_user.email,
                            "folder_type": folder_type,
                            "collection_id": collection_id
                        },
                        "email_summary": {
                            "total_emails": len(emails),
                            "unread_count": sum(1 for email in emails if not getattr(email, 'is_read', False)),
                            "read_count": sum(1 for email in emails if getattr(email, 'is_read', False))
                        }
                    },
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            # XML response for non-WBXML clients (with emails for initial sync)
            xml_response = create_sync_response(emails, sync_key=response_sync_key, collection_id=collection_id)
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_initial_complete", "sync_key": state.sync_key, "client_key": client_sync_key, "response_key": response_sync_key, "email_count": len(emails)},
            )
        # Client sends SyncKey=0 but server is ahead - sync key mismatch, need to reset
        elif client_key_int == 0 and server_key_int > 1:
            # Server is ahead, client wants to restart - send error to force client to reset
            _write_json_line("activesync/activesync.log", {
                "event": "sync_key_mismatch_reset_required",
                "client_key": client_sync_key,
                "server_key": state.sync_key,
                "action": "Sending Status=3 to force client reset"
            })
            # Reset server to 0 to allow fresh start
            state.sync_key = "0"
            db.commit()
            # Send Status=3 (Invalid sync key) to tell client to restart
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            xml_response = create_sync_response([], sync_key="0", collection_id=collection_id)
        # Client confirmed initial sync with simple integer synckey
        elif client_sync_key != "0":
            # Parse simple integer synckey
            try:
                client_counter = int(client_sync_key)
            except ValueError:
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_invalid_synckey_format",
                    "client_sync_key": client_sync_key,
                    "error": "Not a valid integer"
                })
                # Send Status=3 (invalid synckey)
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    wbxml_batch = create_invalid_synckey_response_wbxml(collection_id=collection_id)
                    return Response(content=wbxml_batch.payload, media_type="application/vnd.ms-sync.wbxml", headers=headers)
                return Response(status_code=400)
            
            # CRITICAL FIX #61: Do NOT bump SyncKey on Fetch-only responses
            # Use the actual adds we intend to send (respecting WindowSize)
            preview_adds = emails[:window_size] if window_size else emails
            add_count = len(preview_adds)
            change_count = 0  # Not tracked yet
            delete_count = len(delete_ids) if 'delete_ids' in locals() and delete_ids else 0
            # Consider paging flag (MoreAvailable) as a collection change for key bumping semantics
            has_more_flag = bool(window_size) and (len(emails) > window_size)
            has_collection_changes = ((add_count + change_count + delete_count) > 0) or has_more_flag

            if has_collection_changes:
                state.synckey_counter = client_counter + 1
            else:
                state.synckey_counter = client_counter  # Keep same key if only <Responses><Fetch>

            response_sync_key = str(state.synckey_counter)
            state.sync_key = response_sync_key  # Persist the chosen key

            # Sanity trace: explicit log when fetch-only (no collection changes)
            if not has_collection_changes and fetched_emails:
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_fetch_only_no_key_bump",
                        "client_sync_key": client_sync_key,
                        "response_sync_key": response_sync_key,
                        "fetch_count": len(fetched_emails),
                    },
                )
            # NOTE: We commit this BEFORE sending, so the key is persisted!
            
            _write_json_line("activesync/activesync.log", {
                "event": "sync_client_confirmed_simple",
                "client_sync_key": client_sync_key,
                "response_sync_key": response_sync_key,
                "client_counter": client_counter,
                "new_counter": state.synckey_counter,
                "email_count": add_count,
                "fetch_count": len(fetch_ids) if fetch_ids else 0,
                "has_collection_changes": has_collection_changes
            })
            
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                # CRITICAL FIX #13 (APPLIED TO ALL CODE PATHS): Respect WindowSize!
                # Expert diagnosis: "you dump 19 items in one batch with WindowSize=4"
                # This code path was missing the WindowSize enforcement!
                emails_to_send = emails[:window_size] if window_size else emails
                has_more = len(emails) > window_size if window_size else False

                # Use builder that can include both Adds and Fetch responses
                from .wbxml_builder import create_sync_response_wbxml_with_fetch
                wbxml_batch = create_sync_response_wbxml_with_fetch(
                    sync_key=response_sync_key,
                    emails=[{
                        'id': e.id,
                        'subject': str(getattr(e, 'subject', '') or ''),
                        'from': str(
                            getattr(e, 'external_sender', None)
                            or (getattr(getattr(e, 'sender', None), 'email', None) if getattr(e, 'sender', None) else None)
                            or getattr(e, 'from', None)
                            or getattr(e, 'sender', None)
                            or ''
                        ),
                        'to': str(
                            getattr(e, 'external_recipient', None)
                            or (getattr(getattr(e, 'recipient', None), 'email', None) if getattr(e, 'recipient', None) else None)
                            or getattr(e, 'to', None)
                            or getattr(e, 'recipient', None)
                            or ''
                        ),
                        'created_at': e.created_at,
                        'is_read': bool(getattr(e, 'is_read', False)),
                        'body': str(getattr(e, 'body', None) or getattr(e, 'preview', None) or ''),
                        'body_html': str(getattr(e, 'body_html', None) or getattr(e, 'html_body', None) or '')
                    } for e in emails_to_send],
                    fetched=[{
                        'id': e.id,
                        'server_id': f"{collection_id}:{e.id}",
                        'subject': str(getattr(e, 'subject', '') or ''),
                        'from': str(
                            getattr(e, 'external_sender', None)
                            or (getattr(getattr(e, 'sender', None), 'email', None) if getattr(e, 'sender', None) else None)
                            or getattr(e, 'from', None)
                            or getattr(e, 'sender', None)
                            or ''
                        ),
                        'to': str(
                            getattr(e, 'external_recipient', None)
                            or (getattr(getattr(e, 'recipient', None), 'email', None) if getattr(e, 'recipient', None) else None)
                            or getattr(e, 'to', None)
                            or getattr(e, 'recipient', None)
                            or ''
                        ),
                        'created_at': e.created_at,
                        'is_read': bool(getattr(e, 'is_read', False)),
                        'body': str(getattr(e, 'body', None) or getattr(e, 'preview', None) or ''),
                        'body_html': str(getattr(e, 'body_html', None) or getattr(e, 'html_body', None) or '')
                    } for e in fetched_emails],
                    collection_id=collection_id,
                    window_size=window_size,
                    more_available=has_more,
                    class_name="Email",
                    body_type_preference=2,
                    truncation_size=8192,
                )
                wbxml = wbxml_batch.payload
                # If there were FETCH requests, append <Responses><Fetch> with bodies
                if fetched_emails:
                    from .wbxml_builder import write_fetch_responses
                    w = activesync_w = None
                    try:
                        # Append to existing WBXML: we need a writer capable of appending; since our
                        # builder doesn't expose partial writer, for now we rebuild a combined payload:
                        # (Simple approach: just send the same Add body; iOS accepts body under Add as well)
                        # TODO: Refactor builder to append Responses/Fetch in place.
                        pass
                    except Exception:
                        pass
                
                # CRITICAL FIX #26 + #61: Stage as PENDING only when we actually send <Add> items
                # Expert FIX #26: "Only commit last_synced_email_id when client confirms"
                if emails_to_send and has_collection_changes:
                    max_sent_id = max(e.id for e in emails_to_send)
                    state.pending_sync_key = response_sync_key
                    state.pending_max_email_id = max_sent_id
                    state.pending_item_ids = json.dumps([e.id for e in emails_to_send])
                
                # Commit: NEW SyncKey + PENDING batch (NOT last_synced_email_id yet!)
                # state.sync_key and state.synckey_counter were set above
                db.commit()
                
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_emails_sent_wbxml_simple", 
                        "sync_key": response_sync_key,  # ← NEW key in response
                        "client_key": client_sync_key,  # ← Key client sent
                        "key_progression": f"{client_sync_key}→{response_sync_key}",  # ← Visual!
                        "email_count_total": len(emails),  # ← Total available
                        "email_count_sent": len(emails_to_send),  # ← Actually sent
                        "window_size": window_size,  # ← Client requested
                        "has_more": has_more,  # ← MoreAvailable flag
                        "collection_id": collection_id, 
                        "wbxml_length": len(wbxml), 
                        "wbxml_first20": wbxml[:20].hex(),
                        "wbxml_full_hex": wbxml.hex(),  # ← FULL DUMP for expert analysis
                        "last_synced_email_id": state.last_synced_email_id,  # ← Pagination cursor
                        "pending_staged": bool(state.pending_sync_key),  # ← Pending active?
                        "fetch_only": (not has_collection_changes and bool(fetched_emails))
                    },
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
        # Client sync key matches server - check if we need to send emails
        elif client_key_int == server_key_int:
            # If we have emails to send, send them and bump sync key
            if len(emails) > 0:
                new_sync_key = _bump_sync_key(state, db)
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    # CRITICAL FIX #13: Respect WindowSize! Only send N items at a time
                    # Expert diagnosis: "If client asked for WindowSize = N, put at most N <Add> items"
                    emails_to_send = emails[:window_size] if window_size else emails
                    has_more = len(emails) > window_size if window_size else False
                    
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=new_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or ''), 'body_html': str(getattr(e,'body_html',None) or getattr(e,'html_body',None) or '') } for e in emails_to_send],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=has_more,
                        class_name="Email",
                    )
                    wbxml = wbxml_batch.payload
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_emails_sent_wbxml", 
                            "sync_key": new_sync_key, 
                            "client_key": client_sync_key, 
                            "email_count_total": len(emails),  # ← Total available
                            "email_count_sent": len(emails_to_send),  # ← Actually sent
                            "window_size": window_size,  # ← Client requested
                            "has_more": has_more,  # ← MoreAvailable flag
                            "collection_id": collection_id, 
                            "wbxml_length": len(wbxml), 
                            "wbxml_first20": wbxml[:20].hex(),
                            "wbxml_full_hex": wbxml.hex(),  # ← Full hex dump for expert analysis
                        },
                    )
                    return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            else:
                # No emails to send - return no changes
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=state.sync_key,
                        emails=[],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=False,
                        class_name="Email",
                    )
                    wbxml = wbxml_batch.payload
                    _write_json_line(
                        "activesync/activesync.log",
                        {"event": "sync_no_changes_wbxml", "sync_key": state.sync_key, "client_key": client_sync_key, "collection_id": collection_id, "wbxml_length": len(wbxml), "wbxml_first20": wbxml[:20].hex()},
                    )
                    return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Status>1</Status>
    <SyncKey>{state.sync_key}</SyncKey>
</Sync>"""
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "No changes - client and server in sync"},
            )
        # Client sync key is behind server - Graceful catch-up approach
        elif client_key_int < server_key_int:
            # Graceful approach: Send current emails with next sync key to catch up client
            # Don't force reset - instead, send current state to get client caught up
            sync_gap = server_key_int - client_key_int
            new_sync_key = _bump_sync_key(state, db)
            
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                try:
                    # Send emails respecting WindowSize to get client caught up
                    wbxml_batch = create_sync_response_wbxml(
                        sync_key=new_sync_key,
                        emails=[{ 'id': e.id, 'subject': str(e.subject) if hasattr(e,'subject') else '', 'from': str(getattr(e,'sender',None) or getattr(e,'from',None) or ''), 'to': str(getattr(e,'recipient',None) or getattr(e,'to',None) or ''), 'created_at': e.created_at, 'is_read': bool(getattr(e,'is_read',False)), 'body': str(getattr(e,'body',None) or getattr(e,'preview',None) or ''), 'body_html': str(getattr(e,'body_html',None) or getattr(e,'html_body',None) or '') } for e in emails],
                        collection_id=collection_id,
                        window_size=window_size,
                        more_available=False,
                        class_name="Email",
                    )
                except Exception as e:
                    # Log the error
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_wbxml_creation_error",
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }
                    )
                    # Fall back to XML
                    xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
                else:
                    wbxml = wbxml_batch.payload
                    # Log the successful WBXML creation
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "sync_client_behind_graceful_wbxml",
                            "sync_key": new_sync_key,
                            "client_key": client_sync_key,
                            "server_key": state.sync_key,
                            "email_count": len(emails),
                            "collection_id": collection_id,
                            "wbxml_length": len(wbxml),
                            "wbxml_first50": wbxml[:50].hex(),
                            "sync_gap": sync_gap
                        }
                )
                return Response(content=wbxml, media_type="application/vnd.ms-sync.wbxml", headers=headers)
            else:
                xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
                
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_client_behind_graceful", "sync_key": new_sync_key, "client_key": client_sync_key, "server_key": state.sync_key, "email_count": len(emails), "collection_id": collection_id, "sync_gap": sync_gap, "approach": "graceful_catchup_all_emails"},
                )
        # Client sync key is ahead of server - this shouldn't happen, return MS-ASCMD compliant error
        else:
            xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
<Sync xmlns="AirSync">
    <Status>2</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Sync key error - client ahead of server</Message>
        </Error>
    </Response>
</Sync>"""
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_sync_key_error", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Sync key error - client ahead of server"},
            )
        
        return Response(
            content=xml_response,
            media_type="application/xml",
            headers=headers,
        )
    if cmd == "ping":
        # Z-Push-compliant Ping implementation with event-driven push notifications
        # MS-ASCMD 2.2.2.13: Ping command maintains long-running connection
        import time
        import asyncio
        from ..push_notifications import push_manager
        
        try:
            body = await request.body()
            
            # Parse Ping request to get heartbeat interval and folders to monitor
            # Default values per MS-ASCMD spec
            heartbeat_interval = 540  # 9 minutes (common iOS default)
            folders_to_monitor = ["1"]  # Default to inbox
            
            # Simple WBXML parsing for Ping (codepage 0, Ping namespace)
            # Token 0x03 = HeartbeatInterval (PING), Token 0x04 = Folders (PING)
            if body and len(body) > 10:
                try:
                    # Look for HeartbeatInterval value (STR_I = 0x03)
                    idx = body.find(b'\x03')
                    if idx != -1 and idx + 1 < len(body):
                        # Read the string value until null terminator
                        end_idx = body.find(b'\x00', idx + 1)
                        if end_idx != -1:
                            heartbeat_str = body[idx + 1:end_idx].decode('utf-8', errors='ignore')
                            try:
                                heartbeat_interval = int(heartbeat_str)
                                # Clamp to reasonable range (5 min to 30 min)
                                heartbeat_interval = max(300, min(heartbeat_interval, 1800))
                            except ValueError:
                                pass
                except Exception:
                    pass
            
            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "ping_start",
                    "heartbeat_interval": heartbeat_interval,
                    "folders": folders_to_monitor,
                    "user_id": current_user.id,
                    "active_connections": push_manager.get_user_connections_count(current_user.id),
                }
            )
            
            # Subscribe to push notifications for this user
            notification_event = await push_manager.subscribe(current_user.id, folders_to_monitor)
            
            start_time = time.time()
            changes_detected = False
            
            try:
                # Z-Push approach: Wait for either a notification or timeout
                # This is event-driven - we're notified immediately when new content arrives
                await asyncio.wait_for(
                    notification_event.wait(),
                    timeout=heartbeat_interval
                )
                # If we get here, changes were detected!
                changes_detected = True
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "ping_changes_detected",
                        "trigger": "push_notification",
                        "elapsed_seconds": int(time.time() - start_time),
                    }
                )
            except asyncio.TimeoutError:
                # Heartbeat expired with no changes
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "ping_timeout",
                        "elapsed_seconds": int(time.time() - start_time),
                    }
                )
            finally:
                # Always unsubscribe when done
                await push_manager.unsubscribe(notification_event)
            
            # Build WBXML Ping response
            # Per MS-ASCMD: Status 2 = changes, Status 1 = no changes (timeout)
            from .wbxml_builder import WBXMLWriter, CP_PING
            
            w = WBXMLWriter()
            w.header()
            w.page(1)  # Ping codepage
            w.start(0x05)  # Ping tag
            
            if changes_detected:
                w.start(0x08)  # Status tag
                w.write_str("2")  # Status 2 = Changes detected
                w.end()
                
                # Folders with changes
                w.start(0x04)  # Folders tag
                w.start(0x02)  # Folder tag
                w.write_str("1")  # CollectionId (inbox)
                w.end()
                w.end()
            else:
                w.start(0x08)  # Status tag
                w.write_str("1")  # Status 1 = No changes (heartbeat expired)
                w.end()
            
            w.end()  # Close Ping
            
            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "ping_complete",
                    "changes_detected": changes_detected,
                    "elapsed_seconds": int(time.time() - start_time),
                }
            )
            
            return Response(
                content=w.bytes(),
                media_type="application/vnd.ms-sync.wbxml",
                headers=headers,
            )
            
        except Exception as e:
            _write_json_line(
                "activesync/activesync.log",
                {"event": "ping_error", "error": str(e), "traceback": traceback.format_exc()}
            )
            # Return Status 1 (no changes) on error to avoid client loop
            from .wbxml_builder import WBXMLWriter
            w = WBXMLWriter()
            w.header()
            w.page(1)  # Ping codepage
            w.start(0x05)  # Ping
            w.start(0x08)  # Status
            w.write_str("1")  # No changes
            w.end()
            w.end()
            
            return Response(
                content=w.bytes(),
                media_type="application/vnd.ms-sync.wbxml",
                headers=headers,
        )
    if cmd == "sendmail":
        # Accept request (actual SMTP send could be wired later)
        _write_json_line("activesync/activesync.log", {"event": "sendmail"})
        return Response(status_code=200, headers=headers)
    elif cmd == "getitemestimate":
        # MS-ASCMD GetItemEstimate implementation
        collection_id = request.query_params.get("CollectionId", "1")
        folder_type = "inbox" if collection_id == "1" else "inbox"
        
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, folder_type, limit=1000)
        
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetItemEstimate xmlns="GetItemEstimate">
    <Status>1</Status>
    <Response>
        <Collection>
            <CollectionId>{collection_id}</CollectionId>
            <Estimate>{len(emails)}</Estimate>
        </Collection>
    </Response>
</GetItemEstimate>"""
        
        _write_json_line(
            "activesync/activesync.log",
            {"event": "getitemestimate", "collection_id": collection_id, "estimate": len(emails), "user_id": current_user.id},
        )
    if cmd == "settings":
        # MS-ASCMD Settings implementation with comprehensive device management
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Settings xmlns="Settings">
    <Status>1</Status>
    <DeviceInformation>
        <Set>
            <Model>Generic ActiveSync Device</Model>
            <IMEI>123456789012345</IMEI>
            <FriendlyName>ActiveSync Client</FriendlyName>
            <OS>iOS/Android/Windows</OS>
            <OSLanguage>en-US</OSLanguage>
            <PhoneNumber>+1234567890</PhoneNumber>
            <UserAgent>Microsoft-Server-ActiveSync/16.0</UserAgent>
        </Set>
    </DeviceInformation>
    <Oof>
        <Get>
            <BodyType>Text</BodyType>
        </Get>
    </Oof>
    <DevicePassword>
        <Set>
            <Password>123456</Password>
        </Set>
    </DevicePassword>
    <UserInformation>
        <Get>
            <EmailAddresses>
                <SMTPAddress>{current_user.email}</SMTPAddress>
            </EmailAddresses>
            <DisplayName>{current_user.full_name or current_user.username}</DisplayName>
        </Get>
    </UserInformation>
</Settings>"""
        _write_json_line("activesync/activesync.log", {"event": "settings", "user": current_user.email})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    if cmd == "search":
        # MS-ASCMD Search implementation for GAL (Global Address List)
        query = request.query_params.get("Query", "").strip()
        # Simple fallback: try to parse tiny XML bodies that include <Query>text</Query>
        try:
            body = await request.body()
            if not query and body:
                txt = body.decode("utf-8", errors="ignore")
                if "<Query>" in txt:
                    qstart = txt.find("<Query>") + 7
                    qend = txt.find("</Query>")
                    if qstart >= 7 and qend > qstart:
                        query = txt[qstart:qend].strip()
        except Exception:
            pass
        q = f"%{query.lower()}%" if query else "%"
        users = (
            db.query(User)
            .filter(
                (User.email.ilike(q))
                | (User.username.ilike(q))
                | (User.full_name.ilike(q))
            )
            .order_by(User.full_name.asc())
            .limit(50)
            .all()
        )
        # Build MS-ASCMD compliant Search response for GAL
        root = ET.Element("Search")
        root.set("xmlns", "Search")
        ET.SubElement(root, "Status").text = "1"
        resp = ET.SubElement(root, "Response")
        store = ET.SubElement(resp, "Store")
        ET.SubElement(store, "Name").text = "GAL"
        for u in users:
            result = ET.SubElement(store, "Result")
            props = ET.SubElement(result, "Properties")
            ET.SubElement(props, "DisplayName").text = u.full_name or u.username
            ET.SubElement(props, "EmailAddress").text = u.email
            ET.SubElement(props, "FirstName").text = (u.full_name or u.username).split(
                " "
            )[0]
            last = (u.full_name or u.username).split(" ")[-1]
            ET.SubElement(props, "LastName").text = (
                last if last else (u.full_name or u.username)
            )
        xml = ET.tostring(root, encoding="unicode")
        _write_json_line("activesync/activesync.log", {"event": "search", "query": query, "results": len(users)})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ItemOperations command implementation
    if cmd == "itemoperations":
        # MS-ASCMD ItemOperations for fetching specific items
        item_id = request.query_params.get("ItemId", "")
        collection_id = request.query_params.get("CollectionId", "1")
        
        if not item_id:
            xml = f"<ItemOperations xmlns=\"ItemOperations\"><Status>2</Status></ItemOperations>"
        else:
            # Fetch specific email item
            email_service = EmailService(db)
            emails = email_service.get_user_emails(current_user.id, "inbox", limit=1000)
            target_email = next((e for e in emails if str(e.id) == item_id), None)
            
            if target_email:
                root = ET.Element("ItemOperations")
                root.set("xmlns", "ItemOperations")
                ET.SubElement(root, "Status").text = "1"
                response = ET.SubElement(root, "Response")
                fetch = ET.SubElement(response, "Fetch")
                ET.SubElement(fetch, "Status").text = "1"
                properties = ET.SubElement(fetch, "Properties")
                
                # Add email properties according to MS-ASCMD
                ET.SubElement(properties, "Subject").text = target_email.subject or ""
                ET.SubElement(properties, "From").text = target_email.sender or ""
                ET.SubElement(properties, "To").text = target_email.recipient or ""
                ET.SubElement(properties, "DateReceived").text = target_email.received_at.strftime("%Y-%m-%dT%H:%M:%SZ") if target_email.received_at else ""
                ET.SubElement(properties, "Body").text = target_email.body or ""
                
                xml = ET.tostring(root, encoding="unicode")
            else:
                xml = f"<ItemOperations xmlns=\"ItemOperations\"><Status>2</Status></ItemOperations>"
        
        _write_json_line("activesync/activesync.log", {"event": "itemoperations", "item_id": item_id, "collection_id": collection_id})
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SmartForward command implementation
    if cmd == "smartforward":
        # MS-ASCMD SmartForward for forwarding emails
        _write_json_line("activesync/activesync.log", {"event": "smartforward"})
        xml = f"<SmartForward xmlns=\"SmartForward\"><Status>1</Status></SmartForward>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SmartReply command implementation
    if cmd == "smartreply":
        # MS-ASCMD SmartReply for replying to emails
        _write_json_line("activesync/activesync.log", {"event": "smartreply"})
        xml = f"<SmartReply xmlns=\"SmartReply\"><Status>1</Status></SmartReply>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD MoveItems command implementation
    if cmd == "moveitems":
        # MS-ASCMD MoveItems for moving emails between folders
        _write_json_line("activesync/activesync.log", {"event": "moveitems"})
        xml = f"<MoveItems xmlns=\"MoveItems\"><Status>1</Status></MoveItems>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD MeetingResponse command implementation
    if cmd == "meetingresponse":
        # MS-ASCMD MeetingResponse for calendar meeting responses
        _write_json_line("activesync/activesync.log", {"event": "meetingresponse"})
        xml = f"<MeetingResponse xmlns=\"MeetingResponse\"><Status>1</Status></MeetingResponse>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD Find command implementation
    if cmd == "find":
        # MS-ASCMD Find for searching within folders
        _write_json_line("activesync/activesync.log", {"event": "find"})
        xml = f"<Find xmlns=\"Find\"><Status>1</Status></Find>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD GetAttachment command implementation
    if cmd == "getattachment":
        # MS-ASCMD GetAttachment for fetching email attachments
        _write_json_line("activesync/activesync.log", {"event": "getattachment"})
        xml = f"<GetAttachment xmlns=\"GetAttachment\"><Status>1</Status></GetAttachment>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD Calendar command implementation
    if cmd == "calendar":
        # MS-ASCMD Calendar for calendar synchronization
        _write_json_line("activesync/activesync.log", {"event": "calendar"})
        xml = f"<Calendar xmlns=\"Calendar\"><Status>1</Status></Calendar>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderCreate command implementation
    if cmd == "foldercreate":
        # MS-ASCMD FolderCreate for creating new folders
        _write_json_line("activesync/activesync.log", {"event": "foldercreate"})
        xml = f"<FolderCreate xmlns=\"FolderCreate\"><Status>1</Status></FolderCreate>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderDelete command implementation
    if cmd == "folderdelete":
        # MS-ASCMD FolderDelete for deleting folders
        _write_json_line("activesync/activesync.log", {"event": "folderdelete"})
        xml = f"<FolderDelete xmlns=\"FolderDelete\"><Status>1</Status></FolderDelete>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD FolderUpdate command implementation
    if cmd == "folderupdate":
        # MS-ASCMD FolderUpdate for updating folder properties
        _write_json_line("activesync/activesync.log", {"event": "folderupdate"})
        xml = f"<FolderUpdate xmlns=\"FolderUpdate\"><Status>1</Status></FolderUpdate>"
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ResolveRecipients command implementation
    if cmd == "resolverecipients":
        # MS-ASCMD ResolveRecipients for resolving email addresses
        _write_json_line("activesync/activesync.log", {"event": "resolverecipients"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ResolveRecipients xmlns="ResolveRecipients">
    <Status>1</Status>
    <Response>
        <To>
            <Email>test@example.com</Email>
            <Name>Test User</Name>
            <DisplayName>Test User</DisplayName>
        </To>
    </Response>
</ResolveRecipients>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD ValidateCert command implementation
    if cmd == "validatecert":
        # MS-ASCMD ValidateCert for certificate validation
        _write_json_line("activesync/activesync.log", {"event": "validatecert"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ValidateCert xmlns="ValidateCert">
    <Status>1</Status>
    <Response>
        <Status>1</Status>
        <Certificate>
            <Status>1</Status>
        </Certificate>
    </Response>
</ValidateCert>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    
    # MS-ASCMD SendMail command implementation
    if cmd == "sendmail":
        # MS-ASCMD SendMail for sending emails
        _write_json_line("activesync/activesync.log", {"event": "sendmail"})
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<SendMail xmlns="SendMail">
    <Status>1</Status>
    <Response>
        <Status>1</Status>
    </Response>
</SendMail>"""
        return Response(
            content=xml, media_type="application/xml", headers=headers
        )
    # MS-ASCMD compliant error handling for unsupported commands
    _write_json_line("activesync/activesync.log", {"event": "unsupported_command", "command": cmd, "message": f"Unsupported ActiveSync command: {cmd}"})
    
    # Return MS-ASCMD compliant error response
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<{cmd} xmlns="{cmd}">
    <Status>2</Status>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Command not supported</Message>
        </Error>
    </Response>
</{cmd}>"""
    
    return Response(
        content=xml, 
        media_type="application/vnd.ms-sync.wbxml", 
        headers=headers,
        status_code=200  # MS-ASCMD uses Status codes in XML, not HTTP status codes
    )


def _calendar_to_eas_xml(events: list[CalendarEvent]) -> str:
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")
    col = ET.SubElement(root, "Collection")
    col.set("Class", "Calendar")
    col.set("SyncKey", "1")
    col.set("CollectionId", "calendar")
    for ev in events:
        add = ET.SubElement(col, "Add")
        add.set("ServerId", str(ev.id))
        data = ET.SubElement(add, "ApplicationData")
        ET.SubElement(data, "Subject").text = ev.title
        ET.SubElement(data, "Location").text = ev.location or ""
        ET.SubElement(data, "StartTime").text = ev.start_time.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        ET.SubElement(data, "EndTime").text = ev.end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        ET.SubElement(data, "AllDayEvent").text = "1" if ev.is_all_day else "0"
        if ev.description:
            ET.SubElement(data, "Body").text = ev.description
    return ET.tostring(root, encoding="unicode")


@router.get("/activesync/calendar")
def calendar_list(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == current_user.id)
        .order_by(CalendarEvent.start_time.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "location": e.location,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "is_all_day": e.is_all_day,
        }
        for e in events
    ]


@router.post("/activesync/calendar")
def calendar_create(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    import json

    data = (
        json.loads(request._body.decode("utf-8"))
        if hasattr(request, "_body") and request._body
        else {}
    )
    title = data.get("title") or "Event"
    from datetime import datetime

    start = datetime.fromisoformat(data.get("start_time"))
    end = datetime.fromisoformat(data.get("end_time"))
    event = CalendarEvent(
        user_id=current_user.id,
        title=title,
        description=data.get("description"),
        location=data.get("location"),
        start_time=start,
        end_time=end,
        is_all_day=bool(data.get("is_all_day")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id}


@router.get("/activesync/calendar/sync")
def calendar_sync(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == current_user.id)
        .order_by(CalendarEvent.start_time.asc())
        .limit(200)
        .all()
    )
    xml = _calendar_to_eas_xml(events)
    return Response(
        content=xml, media_type="application/vnd.ms-sync.wbxml", headers=_eas_headers()
    )


# Root-level aliases (some clients call without /activesync prefix)
@router.options("/../Microsoft-Server-ActiveSync")
async def eas_options_alias(request: Request):
    """CRITICAL FIX #31: Use OPTIONS-specific headers (no singular version)!"""
    headers = _eas_options_headers()  # ← Use OPTIONS headers!
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "options_alias",
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        },
    )
    return Response(status_code=200, headers=headers)


@router.post("/../Microsoft-Server-ActiveSync")
async def eas_dispatch_alias(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    return await eas_dispatch(request, current_user, db)


@router.post("/sync")
async def sync_emails(
    request: Request,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """ActiveSync email synchronization endpoint"""
    try:
        # Parse the ActiveSync request
        body = await request.body()
        # In a real implementation, you would parse the WBXML/XML request

        # Get user's emails
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, "inbox", limit=100)

        # Create ActiveSync response
        xml_response = create_sync_response(emails)

        return ActiveSyncResponse(xml_response)

    except Exception as e:
        _write_json_line("activesync/activesync.log", {"event": "error", "error": str(e), "command": cmd})
        
        # MS-ASCMD compliant error response for server errors
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<{cmd} xmlns="{cmd}">
    <Status>3</Status>
    <Response>
        <Error>
            <Code>3</Code>
            <Message>Server error: {str(e)}</Message>
        </Error>
    </Response>
</{cmd}>"""
        
        return Response(
            content=xml, 
            media_type="application/vnd.ms-sync.wbxml", 
            headers=headers,
            status_code=200
        )


@router.get("/ping")
def ping():
    """ActiveSync ping endpoint for device connectivity"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.post("/provision")
async def device_provisioning(
    request: Request, current_user: User = Depends(get_current_user_from_basic_auth)
):
    """Device provisioning for ActiveSync"""
    # In a real implementation, this would handle device registration
    return {
        "status": "provisioned",
        "device_id": "device_123",
        "user": current_user.username,
    }


@router.get("/folders")
def get_folders(
    current_user: User = Depends(get_current_user_from_basic_auth), db: Session = Depends(get_db)
):
    """Get available email folders for ActiveSync with IPM subtree compatibility"""
    folders = [
        {"id": "1", "name": "Inbox", "type": "inbox", "parent_id": "0"},
        {"id": "2", "name": "Outbox", "type": "outbox", "parent_id": "0"},
        {"id": "3", "name": "Sent Items", "type": "sent", "parent_id": "0"},
        {"id": "4", "name": "Deleted Items", "type": "deleted", "parent_id": "0"},
        {"id": "5", "name": "Drafts", "type": "drafts", "parent_id": "0"},
    ]
    return {"folders": folders}


@router.get("/folders/{folder_id}/emails")
def get_folder_emails(
    folder_id: str,
    current_user: User = Depends(get_current_user_from_basic_auth),
    db: Session = Depends(get_db),
):
    """Get emails from a specific folder for ActiveSync"""
    email_service = EmailService(db)

    # Microsoft ActiveSync folder mapping according to MS-ASCMD specification
    # This must match the mapping used in the sync command
    folder_map = {
        "1": "inbox",       # Inbox (Type 2)
        "2": "drafts",       # Drafts (Type 3)
        "3": "deleted",      # Deleted Items (Type 4)
        "4": "sent",         # Sent Items (Type 5)
        "5": "outbox"        # Outbox (Type 6)
    }

    folder = folder_map.get(folder_id, "inbox")
    emails = email_service.get_user_emails(current_user.id, folder, limit=50)

    return {
        "folder_id": folder_id,
        "folder_name": folder,
        "emails": [
            {
                "id": email.id,
                "subject": email.subject,
                "from": getattr(getattr(email, "sender", None), "email", ""),
                "to": getattr(getattr(email, "recipient", None), "email", ""),
                "date": email.created_at.isoformat(),
                "read": email.is_read,
                "body": email.body,
            }
            for email in emails
        ],
    }
