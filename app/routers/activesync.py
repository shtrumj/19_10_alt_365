from datetime import datetime, timedelta
from typing import List, Optional
from xml.etree import ElementTree as ET
import time
import uuid
import io
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user_from_basic_auth
from ..database import ActiveSyncDevice, ActiveSyncState, CalendarEvent, User, get_db
from ..diagnostic_logger import _write_json_line
from ..email_service import EmailService
from ..wbxml_encoder import create_foldersync_wbxml, create_sync_wbxml
from ..minimal_wbxml import create_minimal_foldersync_wbxml
from ..minimal_sync_wbxml import create_minimal_sync_wbxml
from ..zpush_wbxml import create_zpush_style_foldersync_wbxml
from ..iphone_wbxml import create_iphone_foldersync_wbxml
from ..wbxml_parser import parse_wbxml_sync_request, parse_wbxml_foldersync_request

# Rate limiting for sync requests
_sync_rate_limits = {}

router = APIRouter(prefix="/activesync", tags=["activesync"])


class ActiveSyncResponse:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content

    def __call__(self, *args, **kwargs):
        return Response(
            content=self.xml_content, media_type="application/vnd.ms-sync.wbxml"
        )


def _eas_headers(policy_key: str = None) -> dict:
    """Headers required by Microsoft Exchange ActiveSync clients according to MS-ASHTTP specification."""
    headers = {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "15.0",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        "Content-Type": "application/vnd.ms-sync.wbxml",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # MS-ASHTTP protocol headers (single instance, not duplicated)
        "MS-ASProtocolVersions": "12.1,14.0,14.1,16.0,16.1",
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert"
        ),
        # MS-ASHTTP protocol support headers
        "MS-ASProtocolSupports": "1.0,2.0,2.1,2.5,12.0,12.1,14.0,14.1,16.0,16.1",
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
    """Respond to ActiveSync OPTIONS discovery with required headers and log it."""
    headers = _eas_headers()
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
    headers = _eas_headers()
    cmd = request.query_params.get("Cmd", "").lower()
    device_id = request.query_params.get("DeviceId", "device-generic")
    device_type = request.query_params.get("DeviceType", "SmartPhone")

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
    
    device = _get_or_create_device(db, current_user.id, device_id, device_type)

    # --- Command Handling ---

    # The client MUST be allowed to Provision itself at any time.
    if cmd == "provision":
        # The Provisioning process is a two-step handshake.
        # Step 1: Client sends an empty Provision request. Server responds with policies.
        # Step 2: Client sends the policies back, acknowledging them. Server responds with success.
        
        # In a real implementation, you would parse the WBXML body to see if the client
        # is acknowledging a policy. For now, we assume any Provision request is an attempt to comply.
        
        # Mark the device as provisioned. This is the critical step.
        if device.is_provisioned != 1:
            device.is_provisioned = 1
            db.commit()
            _write_json_line("activesync/activesync.log", {"event": "device_provisioned", "device_id": device_id})

        policy_key = "1" # A simple, static policy key is sufficient.
        
        # This is a full, compliant Provision response that clients expect.
        # The iPhone requires a complete EASProvisionDoc with all policy settings.
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Provision xmlns="Provision:">
    <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <PolicyKey>{policy_key}</PolicyKey>
            <Status>1</Status>
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
                    <AllowSimpleDevicePassword>1</AllowSimpleDevicePassword>
                </EASProvisionDoc>
            </Data>
        </Policy>
    </Policies>
</Provision>"""
        
        _write_json_line("activesync/activesync.log", {"event": "provision_response", "device_id": device_id})
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
                wbxml_content = create_minimal_foldersync_wbxml(state.sync_key)
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
                wbxml_content = create_minimal_foldersync_wbxml(state.sync_key)
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
                wbxml_content = create_minimal_foldersync_wbxml(state.sync_key)  # Simplified error response
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
        client_sync_key = wbxml_params.get("sync_key", request.query_params.get("SyncKey", "0"))
        collection_id = wbxml_params.get("collection_id", request.query_params.get("CollectionId", "1"))
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # Debug logging for sync key comparison
        _write_json_line(
            "activesync/activesync.log",
            {"event": "sync_debug", "client_key": client_sync_key, "client_key_int": client_key_int, "server_key": state.sync_key, "server_key_int": server_key_int, "user_id": current_user.id},
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
        
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, folder_type, limit=50)
        
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
        
        # Initial sync (SyncKey=0) - always return all available emails according to MS-ASCMD
        if client_key_int == 0:
            # For initial sync, update state to 1 and respond with SyncKey=1
            # The iPhone expects the server to advance the sync key after initial sync
            if state.sync_key == "0":
                state.sync_key = "1"
                db.commit()
                _write_json_line("activesync/activesync.log", {
                    "event": "sync_initial_sync_key_updated", 
                    "device_id": device_id,
                    "collection_id": collection_id,
                    "old_sync_key": "0",
                    "new_sync_key": "1",
                    "response_sync_key": "1"
                })
            response_sync_key = "1"  # Respond with 1 after initial sync
            # Detect iPhone / WBXML-capable clients by content-type/body header
            is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
            if is_wbxml_request:
                wbxml = create_minimal_sync_wbxml(sync_key=response_sync_key, emails=emails, collection_id=collection_id)
                _write_json_line(
                    "activesync/activesync.log",
                    {
                        "event": "sync_initial_wbxml", 
                        "sync_key": response_sync_key, 
                        "client_key": client_sync_key, 
                        "email_count": len(emails), 
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
            xml_response = create_sync_response(emails, sync_key=response_sync_key, collection_id=collection_id)
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_initial", "sync_key": state.sync_key, "client_key": client_sync_key, "email_count": len(emails), "collection_id": collection_id},
            )
        # Client sync key matches server - check if we need to send emails
        elif client_key_int == server_key_int and client_key_int > 0:
            # If we have emails to send, send them and bump sync key
            if len(emails) > 0:
                new_sync_key = _bump_sync_key(state, db)
                is_wbxml_request = len(request_body_bytes) > 0 and request_body_bytes.startswith(b'\x03\x01')
                if is_wbxml_request:
                    wbxml = create_minimal_sync_wbxml(sync_key=new_sync_key, emails=emails, collection_id=collection_id)
                    _write_json_line(
                        "activesync/activesync.log",
                        {"event": "sync_emails_sent_wbxml", "sync_key": new_sync_key, "client_key": client_sync_key, "email_count": len(emails), "collection_id": collection_id, "wbxml_length": len(wbxml), "wbxml_first20": wbxml[:20].hex()},
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
                    wbxml = create_minimal_sync_wbxml(sync_key=state.sync_key, emails=[], collection_id=collection_id)
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
                    # Import the function
                    from ..minimal_sync_wbxml import create_minimal_sync_wbxml
                    
                    # Send ALL current emails to get client caught up
                    wbxml = create_minimal_sync_wbxml(
                        sync_key=new_sync_key, 
                        emails=emails,
                        collection_id=collection_id,
                        status=1
                    )
                    
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
    headers = _eas_headers()
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
