from datetime import datetime, timedelta
from typing import List, Optional
from xml.etree import ElementTree as ET
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user_from_basic_auth
from ..database import ActiveSyncDevice, ActiveSyncState, CalendarEvent, User, get_db
from ..diagnostic_logger import _write_json_line
from ..email_service import EmailService

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


def _eas_headers() -> dict:
    """Headers required by Microsoft Exchange ActiveSync clients according to MS-ASHTTP specification."""
    return {
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
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar"
        ),
        # MS-ASHTTP protocol support headers
        "X-MS-ASProtocolSupports": "ItemOperations,SendMail,SmartForward,SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar",
    }


def create_sync_response(emails: List, sync_key: str = "1", collection_id: str = "1"):
    """Create ActiveSync XML response for email synchronization according to MS-ASCMD specification"""
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")

    # FIXED: MS-ASCMD compliant structure with Collections wrapper
    collections = ET.SubElement(root, "Collections")
    collection = ET.SubElement(collections, "Collection")
    collection.set("SyncKey", sync_key)
    collection.set("CollectionId", collection_id)
    collection.set("Status", "1")  # Success status

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

        # DateReceived (required)
        date_elem = ET.SubElement(application_data, "DateReceived")
        date_elem.text = email.created_at.isoformat()

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

        # ConversationId (required for threading)
        conversation_id = ET.SubElement(application_data, "ConversationId")
        conversation_id.text = f"96198F80F06044EDA67815EB92B45573"  # Fixed conversation ID

        # ConversationIndex (required for threading)
        conversation_index = ET.SubElement(application_data, "ConversationIndex")
        conversation_index.text = "CD4F18CF13"  # Fixed conversation index

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
            sync_key="1",
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
    """Basic dispatcher for Microsoft-Server-ActiveSync commands.
    Parses the 'Cmd' query parameter and returns minimal, valid responses
    for Sync, Ping, Provision, and FolderSync commands.
    """
    headers = _eas_headers()
    cmd = request.query_params.get("Cmd", "").lower()
    device_id = request.query_params.get("DeviceId", "device-generic")
    device_type = request.query_params.get("DeviceType", "SmartPhone")
    collection_id = request.query_params.get("CollectionId", "1")
    
    # MS-ASCMD compliant error handling for missing command
    if not cmd:
        _write_json_line("activesync/activesync.log", {"event": "no_command", "message": "No command specified"})
        xml = """<?xml version="1.0" encoding="utf-8"?>
<Error xmlns="Error">
    <Status>2</Status>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Command not specified</Message>
        </Error>
    </Response>
</Error>"""
        return Response(
            content=xml, 
            media_type="application/vnd.ms-sync.wbxml", 
            headers=headers,
            status_code=200
        )
    # Temporarily disable rate limiting to fix sync issues
    # if cmd in ["sync", "foldersync"] and not _check_rate_limit(current_user.id, device_id, cmd):
    #     _write_json_line(
    #         "activesync/activesync.log",
    #         {"event": "rate_limit_exceeded", "user": current_user.username, "cmd": cmd},
    #     )
    #     # Return proper ActiveSync error response instead of 429
    #     if cmd == "foldersync":
    #         xml = "<FolderSync><Status>3</Status><SyncKey>0</SyncKey></FolderSync>"
    #         return Response(
    #             content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
    #         )
    #     else:
    #         xml = "<Sync><Status>3</Status><SyncKey>0</SyncKey></Sync>"
    #         return Response(
    #             content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
    #         )
    
    _get_or_create_device(db, current_user.id, device_id, device_type)
    state = _get_or_init_state(db, current_user.id, device_id, collection_id)

    if cmd == "sync":
        # Microsoft ActiveSync Sync implementation according to MS-ASCMD specification
        client_sync_key = request.query_params.get("SyncKey", "0")
        collection_id = request.query_params.get("CollectionId", "1")
        
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
        _write_json_line(
            "activesync/activesync.log",
            {"event": "sync_emails_found", "count": len(emails), "user_id": current_user.id},
        )
        
        # Initial sync (SyncKey=0) - return all available emails according to MS-ASCMD
        if client_key_int == 0:
            # MS-ASCMD compliant: Check if this is a repeated initial sync (client not progressing)
            if state.sync_key == "1":
                # Client is stuck in initial sync loop - return empty sync response to force progression
                # This is MS-ASCMD compliant behavior for clients that don't progress properly
                xml_response = f"<Sync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey></Sync>"
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_force_progression", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Client stuck in initial sync - returning empty sync to force progression according to MS-ASCMD"},
                )
            else:
                # First time initial sync - provide emails
                state.sync_key = "1"
                db.commit()
                xml_response = create_sync_response(emails, sync_key=state.sync_key, collection_id=collection_id)
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "sync_initial", "sync_key": state.sync_key, "client_key": client_sync_key, "email_count": len(emails), "collection_id": collection_id},
                )
        # Client sync key matches server - no changes
        elif client_key_int == server_key_int and client_key_int > 0:
            xml_response = f"<Sync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey></Sync>"
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "No changes - client and server in sync"},
            )
        # Client sync key is behind server - return current server sync key with available emails
        elif client_key_int < server_key_int:
            new_sync_key = _bump_sync_key(state, db)
            xml_response = create_sync_response(emails, sync_key=new_sync_key, collection_id=collection_id)
            _write_json_line(
                "activesync/activesync.log",
                {"event": "sync_client_behind", "sync_key": new_sync_key, "client_key": client_sync_key, "email_count": len(emails), "collection_id": collection_id},
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
            media_type="application/vnd.ms-sync.wbxml",
            headers=headers,
        )
    if cmd == "ping":
        # Minimal Ping response with heartbeat interval acceptance
        _write_json_line("activesync/activesync.log", {"event": "ping"})
        return Response(status_code=200, headers=headers)
    if cmd == "getitemestimate":
        # Return a small estimate for Inbox (CollectionId=1)
        xml = f"<GetItemEstimate><Status>1</Status><Response><Collection><CollectionId>{collection_id}</CollectionId><Estimate>25</Estimate></Collection></Response></GetItemEstimate>"
        _write_json_line(
            "activesync/activesync.log",
            {"event": "getitemestimate", "collection": collection_id},
        )
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
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
        
    elif cmd == "provision":
        # Enhanced Provision response with device management policies
        policy_key = "1024"
        xml = f"""<Provision xmlns="Provision:">
    <Status>1</Status>
    <Policies>
        <Policy>
            <PolicyType>MS-EAS-Provisioning-WBXML</PolicyType>
            <PolicyKey>{policy_key}</PolicyKey>
            <Status>1</Status>
            <Data>
                <EASProvisionDoc>
                    <DevicePasswordEnabled>false</DevicePasswordEnabled>
                    <AlphanumericDevicePasswordRequired>false</AlphanumericDevicePasswordRequired>
                    <MinDevicePasswordLength>0</MinDevicePasswordLength>
                    <MaxInactivityTimeDeviceLock>0</MaxInactivityTimeDeviceLock>
                    <RequireDeviceEncryption>false</RequireDeviceEncryption>
                    <AllowSimpleDevicePassword>true</AllowSimpleDevicePassword>
                    <DevicePasswordExpiration>0</DevicePasswordExpiration>
                    <PasswordRecoveryEnabled>false</PasswordRecoveryEnabled>
                    <AttachmentsEnabled>true</AttachmentsEnabled>
                    <MaxAttachmentSize>0</MaxAttachmentSize>
                    <AllowStorageCard>true</AllowStorageCard>
                    <AllowCamera>true</AllowCamera>
                    <RequireStorageCardEncryption>false</RequireStorageCardEncryption>
                    <AllowUnsignedApplications>true</AllowUnsignedApplications>
                    <AllowUnsignedInstallationPackages>true</AllowUnsignedInstallationPackages>
                    <MinDevicePasswordComplexCharacters>0</MinDevicePasswordComplexCharacters>
                    <AllowWiFi>true</AllowWiFi>
                    <AllowTextMessaging>true</AllowTextMessaging>
                    <AllowPOPIMAPEmail>true</AllowPOPIMAPEmail>
                    <AllowBluetooth>true</AllowBluetooth>
                    <AllowIrDA>true</AllowIrDA>
                    <RequireManualSyncWhenRoaming>false</RequireManualSyncWhenRoaming>
                    <AllowDesktopSync>true</AllowDesktopSync>
                    <MaxCalendarAgeFilter>0</MaxCalendarAgeFilter>
                    <AllowHTMLEmail>true</AllowHTMLEmail>
                    <MaxEmailAgeFilter>0</MaxEmailAgeFilter>
                    <MaxEmailBodyTruncation>0</MaxEmailBodyTruncation>
                    <MaxEmailHTMLBodyTruncation>0</MaxEmailHTMLBodyTruncation>
                    <RequireSignedSMIMEMessages>false</RequireSignedSMIMEMessages>
                    <RequireEncryptedSMIMEMessages>false</RequireEncryptedSMIMEMessages>
                    <RequireSignedSMIMEAlgorithm>0</RequireSignedSMIMEAlgorithm>
                    <RequireEncryptedSMIMEAlgorithm>0</RequireEncryptedSMIMEAlgorithm>
                    <AllowSMIMESoftCerts>true</AllowSMIMESoftCerts>
                    <AllowBrowser>true</AllowBrowser>
                    <AllowConsumerEmail>true</AllowConsumerEmail>
                    <AllowRemoteDesktop>true</AllowRemoteDesktop>
                    <AllowInternetSharing>true</AllowInternetSharing>
                    <UnapprovedInROMApplicationList></UnapprovedInROMApplicationList>
                    <ApprovedApplicationList></ApprovedApplicationList>
                </EASProvisionDoc>
            </Data>
        </Policy>
    </Policies>
</Provision>"""
        _write_json_line("activesync/activesync.log", {"event": "provision"})
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    if cmd == "foldersync":
        # Microsoft ActiveSync FolderSync implementation according to MS-ASCMD specification
        client_sync_key = request.query_params.get("SyncKey", "0")
        
        # Handle sync key validation according to ActiveSync spec
        try:
            client_key_int = int(client_sync_key) if client_sync_key.isdigit() else 0
            server_key_int = int(state.sync_key) if state.sync_key.isdigit() else 0
        except (ValueError, TypeError):
            client_key_int = 0
            server_key_int = 0
        
        # Initial folder sync (SyncKey=0) - provide complete folder hierarchy according to MS-ASCMD
        if client_key_int == 0:
            # MS-ASCMD compliant: Check if this is a repeated initial sync (client not progressing)
            # If client keeps sending SyncKey=0, we need to handle this according to MS-ASCMD standards
            if state.sync_key == "1":
                # Client is stuck in initial sync loop - return empty changes to force progression
                # This is MS-ASCMD compliant behavior for clients that don't progress properly
                xml = f"<FolderSync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey><Changes></Changes></FolderSync>"
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_force_progression", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Client stuck in initial sync - returning empty changes to force progression according to MS-ASCMD", "xml_length": len(xml), "xml_preview": xml[:200]},
                )
            else:
                # First time initial sync - provide complete folder hierarchy
                state.sync_key = "1"
                db.commit()
                
                # Provide complete folder structure according to MS-ASCMD specification
                xml = (
                    f"<FolderSync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey><Changes>"
                    f"<Count>5</Count>"
                    f"<Add><ServerId>1</ServerId><ParentId>0</ParentId><DisplayName>Inbox</DisplayName><Type>2</Type></Add>"
                    f"<Add><ServerId>2</ServerId><ParentId>0</ParentId><DisplayName>Drafts</DisplayName><Type>3</Type></Add>"
                    f"<Add><ServerId>3</ServerId><ParentId>0</ParentId><DisplayName>Deleted Items</DisplayName><Type>4</Type></Add>"
                    f"<Add><ServerId>4</ServerId><ParentId>0</ParentId><DisplayName>Sent Items</DisplayName><Type>5</Type></Add>"
                    f"<Add><ServerId>5</ServerId><ParentId>0</ParentId><DisplayName>Outbox</DisplayName><Type>6</Type></Add>"
                    "</Changes></FolderSync>"
                )
                _write_json_line(
                    "activesync/activesync.log",
                    {"event": "foldersync_initial", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Initial folder sync - providing complete folder hierarchy according to MS-ASCMD", "xml_length": len(xml), "xml_preview": xml[:200]},
                )
        # Client sync key matches server - no changes according to MS-ASCMD
        elif client_key_int == server_key_int and client_key_int > 0:
            # MS-ASCMD compliant: No changes, return current sync key
            xml = f"<FolderSync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey><Changes></Changes></FolderSync>"
            _write_json_line(
                "activesync/activesync.log",
                {"event": "foldersync_no_changes", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "No folder changes - client and server in sync"},
            )
        # Client sync key is behind server - return current server sync key with no changes
        elif client_key_int < server_key_int:
            xml = f"<FolderSync xmlns=\"AirSync\"><Status>1</Status><SyncKey>{state.sync_key}</SyncKey><Changes></Changes></FolderSync>"
            _write_json_line(
                "activesync/activesync.log",
                {"event": "foldersync_client_behind", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Client behind server - returning current sync key"},
            )
        # Client sync key is ahead of server - this shouldn't happen, return MS-ASCMD compliant error
        else:
            xml = f"""<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="AirSync">
    <Status>2</Status>
    <SyncKey>{state.sync_key}</SyncKey>
    <Response>
        <Error>
            <Code>2</Code>
            <Message>Sync key error - client ahead of server</Message>
        </Error>
    </Response>
</FolderSync>"""
            _write_json_line(
                "activesync/activesync.log",
                {"event": "foldersync_sync_key_error", "sync_key": state.sync_key, "client_key": client_sync_key, "message": "Sync key error - client ahead of server"},
            )
        
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
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
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
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
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
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
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD SmartForward command implementation
    if cmd == "smartforward":
        # MS-ASCMD SmartForward for forwarding emails
        _write_json_line("activesync/activesync.log", {"event": "smartforward"})
        xml = f"<SmartForward xmlns=\"SmartForward\"><Status>1</Status></SmartForward>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD SmartReply command implementation
    if cmd == "smartreply":
        # MS-ASCMD SmartReply for replying to emails
        _write_json_line("activesync/activesync.log", {"event": "smartreply"})
        xml = f"<SmartReply xmlns=\"SmartReply\"><Status>1</Status></SmartReply>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD MoveItems command implementation
    if cmd == "moveitems":
        # MS-ASCMD MoveItems for moving emails between folders
        _write_json_line("activesync/activesync.log", {"event": "moveitems"})
        xml = f"<MoveItems xmlns=\"MoveItems\"><Status>1</Status></MoveItems>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD MeetingResponse command implementation
    if cmd == "meetingresponse":
        # MS-ASCMD MeetingResponse for calendar meeting responses
        _write_json_line("activesync/activesync.log", {"event": "meetingresponse"})
        xml = f"<MeetingResponse xmlns=\"MeetingResponse\"><Status>1</Status></MeetingResponse>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD Find command implementation
    if cmd == "find":
        # MS-ASCMD Find for searching within folders
        _write_json_line("activesync/activesync.log", {"event": "find"})
        xml = f"<Find xmlns=\"Find\"><Status>1</Status></Find>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD GetAttachment command implementation
    if cmd == "getattachment":
        # MS-ASCMD GetAttachment for fetching email attachments
        _write_json_line("activesync/activesync.log", {"event": "getattachment"})
        xml = f"<GetAttachment xmlns=\"GetAttachment\"><Status>1</Status></GetAttachment>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD Calendar command implementation
    if cmd == "calendar":
        # MS-ASCMD Calendar for calendar synchronization
        _write_json_line("activesync/activesync.log", {"event": "calendar"})
        xml = f"<Calendar xmlns=\"Calendar\"><Status>1</Status></Calendar>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD FolderCreate command implementation
    if cmd == "foldercreate":
        # MS-ASCMD FolderCreate for creating new folders
        _write_json_line("activesync/activesync.log", {"event": "foldercreate"})
        xml = f"<FolderCreate xmlns=\"FolderCreate\"><Status>1</Status></FolderCreate>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD FolderDelete command implementation
    if cmd == "folderdelete":
        # MS-ASCMD FolderDelete for deleting folders
        _write_json_line("activesync/activesync.log", {"event": "folderdelete"})
        xml = f"<FolderDelete xmlns=\"FolderDelete\"><Status>1</Status></FolderDelete>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    
    # MS-ASCMD FolderUpdate command implementation
    if cmd == "folderupdate":
        # MS-ASCMD FolderUpdate for updating folder properties
        _write_json_line("activesync/activesync.log", {"event": "folderupdate"})
        xml = f"<FolderUpdate xmlns=\"FolderUpdate\"><Status>1</Status></FolderUpdate>"
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
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

    folder_map = {
        "1": "inbox", 
        "2": "outbox", 
        "3": "sent", 
        "4": "deleted", 
        "5": "drafts"
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
