from datetime import datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import ActiveSyncDevice, ActiveSyncState, CalendarEvent, User, get_db
from ..diagnostic_logger import _write_json_line
from ..email_service import EmailService

router = APIRouter(prefix="/activesync", tags=["activesync"])


class ActiveSyncResponse:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content

    def __call__(self, *args, **kwargs):
        return Response(
            content=self.xml_content, media_type="application/vnd.ms-sync.wbxml"
        )


def _eas_headers() -> dict:
    """Headers required by Microsoft Exchange ActiveSync clients."""
    return {
        # Protocol identification and version support
        "MS-Server-ActiveSync": "15.0",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # Commonly advertised versions and commands
        "MS-ASProtocolVersions": "12.1,14.0,14.1,16.0,16.1",
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar"
        ),
    }


def create_sync_response(emails: List, sync_key: str = "1"):
    """Create ActiveSync XML response for email synchronization"""
    root = ET.Element("Sync")
    root.set("xmlns", "AirSync")

    # Add collection
    collection = ET.SubElement(root, "Collection")
    collection.set("Class", "Email")
    collection.set("SyncKey", sync_key)
    collection.set("CollectionId", "1")

    # Add commands for each email
    for email in emails:
        add = ET.SubElement(collection, "Add")
        add.set("ServerId", str(email.id))

        # Email properties
        application_data = ET.SubElement(add, "ApplicationData")

        # Subject
        subject_elem = ET.SubElement(application_data, "Subject")
        subject_elem.text = email.subject

        # From
        from_elem = ET.SubElement(application_data, "From")
        from_elem.text = getattr(getattr(email, "sender", None), "email", "")

        # To
        to_elem = ET.SubElement(application_data, "To")
        to_elem.text = getattr(getattr(email, "recipient", None), "email", "")

        # Body
        if email.body:
            body_elem = ET.SubElement(application_data, "Body")
            body_elem.text = email.body

        # Date
        date_elem = ET.SubElement(application_data, "DateReceived")
        date_elem.text = email.created_at.isoformat()

        # Read status
        read_elem = ET.SubElement(application_data, "Read")
        read_elem.text = "1" if email.is_read else "0"

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
    return state


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
    current_user: User = Depends(get_current_user),
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
    _get_or_create_device(db, current_user.id, device_id, device_type)
    state = _get_or_init_state(db, current_user.id, device_id, collection_id)

    if cmd == "sync":
        # Simple incremental: bump key and return emails
        email_service = EmailService(db)
        emails = email_service.get_user_emails(current_user.id, "inbox", limit=100)
        xml_response = create_sync_response(emails, sync_key=_bump_sync_key(state, db))
        _write_json_line(
            "activesync/activesync.log",
            {"event": "sync_response", "bytes": len(xml_response)},
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
    if cmd == "provision":
        # Minimal Provision acknowledgement with PolicyKey echo
        policy_key = "1024"
        xml = f"<Provision><Status>1</Status><Policies><Policy><PolicyType>MS-EAS-Provisioning-WBXML</PolicyType><PolicyKey>{policy_key}</PolicyKey><Status>1</Status></Policy></Policies></Provision>"
        _write_json_line("activesync/activesync.log", {"event": "provision"})
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    if cmd == "foldersync":
        # Minimal FolderSync response with Inbox as CollectionId=1
        xml = (
            f"<FolderSync><Status>1</Status><SyncKey>{state.sync_key}</SyncKey><Changes>"
            f"<Add><ServerId>{collection_id}</ServerId><ParentId>0</ParentId><DisplayName>Inbox</DisplayName><Type>2</Type></Add>"
            "</Changes></FolderSync>"
        )
        _write_json_line(
            "activesync/activesync.log",
            {"event": "foldersync", "sync_key": state.sync_key},
        )
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    if cmd == "settings":
        # Minimal Settings response enabling Calendar
        xml = "<Settings><Status>1</Status><DeviceInformation><Set><Model>Generic</Model></Set></DeviceInformation></Settings>"
        _write_json_line("activesync/activesync.log", {"event": "settings"})
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    if cmd == "search":
        # Implement GAL (Global Address List) search
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
        # Build EAS Search response for GAL
        root = ET.Element("Search")
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
        return Response(
            content=xml, media_type="application/vnd.ms-sync.wbxml", headers=headers
        )
    # Unsupported command
    return Response(status_code=501, headers=headers)


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
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await eas_dispatch(request, current_user, db)


@router.post("/sync")
async def sync_emails(
    request: Request,
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(status_code=500, detail=f"ActiveSync error: {str(e)}")


@router.get("/ping")
def ping():
    """ActiveSync ping endpoint for device connectivity"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.post("/provision")
async def device_provisioning(
    request: Request, current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get available email folders for ActiveSync"""
    folders = [
        {"id": "1", "name": "Inbox", "type": "inbox"},
        {"id": "2", "name": "Sent Items", "type": "sent"},
        {"id": "3", "name": "Deleted Items", "type": "deleted"},
    ]
    return {"folders": folders}


@router.get("/folders/{folder_id}/emails")
def get_folder_emails(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get emails from a specific folder for ActiveSync"""
    email_service = EmailService(db)

    folder_map = {"1": "inbox", "2": "sent", "3": "deleted"}

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
