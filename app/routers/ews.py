import base64
import re

from fastapi import APIRouter, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import authenticate_user
from ..database import Email, EmailAttachment, SessionLocal
from ..diagnostic_logger import log_ews
from ..email_delivery import email_delivery
from ..ews_push import ews_push_hub

router = APIRouter(prefix="/EWS", tags=["ews"])

# Basic, minimal SOAP envelope helpers
EWS_NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
EWS_NS_TYPES = "http://schemas.microsoft.com/exchange/services/2006/types"
EWS_NS_MESSAGES = "http://schemas.microsoft.com/exchange/services/2006/messages"


def soap_envelope(body_xml: str) -> str:
    header_xml = (
        f'<s:Header><t:ServerVersionInfo xmlns:t="{EWS_NS_TYPES}" '
        f'MajorVersion="15" MinorVersion="1" '
        f'MajorBuildNumber="1531" MinorBuildNumber="3" '
        f'Version="V2_23"/></s:Header>'
    )
    return f"""
<s:Envelope xmlns:s="{EWS_NS_SOAP}">
  {header_xml}
  <s:Body>
    {body_xml}
  </s:Body>
</s:Envelope>
""".strip()


def ews_error(message: str) -> str:
    inner = f'<m:ResponseCode xmlns:m="{EWS_NS_MESSAGES}">ErrorInternalServerError</m:ResponseCode><m:MessageText xmlns:m="{EWS_NS_MESSAGES}">{message}</m:MessageText>'
    return soap_envelope(
        f'<m:ResponseMessages xmlns:m="{EWS_NS_MESSAGES}">{inner}</m:ResponseMessages>'
    )


@router.get("/Exchange.asmx")
@router.post("/Exchange.asmx")
async def ews_aspx(request: Request):
    """Very minimal EWS endpoint to make Outlook probe pass. Supports FindItem on Inbox with a tiny response.
    This is not a full EWS; it only returns a small item list mapped from DB.
    """
    db: Session = SessionLocal()
    try:
        # Basic authentication enforcement similar to IIS EWS behavior
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            log_ews("auth_challenge", {"present": bool(auth_header)})
            return Response(
                content="",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={
                    "WWW-Authenticate": 'Basic realm="EWS"',
                    "Connection": "close",
                },
            )

        try:
            decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            log_ews("auth_decode_error", {})
            return Response(
                content="",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={
                    "WWW-Authenticate": 'Basic realm="EWS"',
                    "Connection": "close",
                },
            )

        user = authenticate_user(db, username, password)
        if not user:
            log_ews("auth_invalid", {"username": username})
            return Response(
                content="",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={
                    "WWW-Authenticate": 'Basic realm="EWS"',
                    "Connection": "close",
                },
            )

        raw = await request.body()
        ua = request.headers.get("User-Agent")
        preview = raw.decode("utf-8", errors="ignore")
        log_ews(
            "request",
            {
                "ua": ua,
                "preview": preview[:1000],
            },
        )

        text = preview

        operation_name = "Unknown"
        try:
            op_match = re.search(
                r"<(?:soap|s):Body[^>]*>\s*<([\w:]+)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if op_match:
                operation_name = op_match.group(1).split(":")[-1]
        except Exception:
            operation_name = "Unknown"
        log_ews("operation_detected", {"operation": operation_name})

        # Naive routing based on method names in SOAP
        def _xml(s: str) -> str:
            if s is None:
                return ""
            return (
                str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )

        def _as_email(val, fallback: str = "") -> str:
            try:
                if not val:
                    return fallback
                if isinstance(val, str):
                    return val
                for attr in ("email", "user_email", "address", "mail"):
                    v = getattr(val, attr, None)
                    if isinstance(v, str) and v:
                        return v
                return fallback or str(val)
            except Exception:
                return fallback

        if "FindFolder" in text or "<m:FindFolder" in text:
            # Return a shallow listing of default folders under msgfolderroot
            # Include mail, contacts, and calendar folders with minimal metadata
            def f_mail(fid: str, name: str) -> str:
                return (
                    f"<t:Folder>"
                    f'<t:FolderId Id="DF_{fid}" ChangeKey="0"/>'
                    f"<t:DisplayName>{name}</t:DisplayName>"
                    f"<t:FolderClass>IPF.Note</t:FolderClass>"
                    f'<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                    f"<t:TotalCount>0</t:TotalCount>"
                    f"<t:ChildFolderCount>0</t:ChildFolderCount>"
                    f"</t:Folder>"
                )

            folders_xml = (
                f_mail("inbox", "Inbox")
                + f_mail("drafts", "Drafts")
                + f_mail("sentitems", "Sent Items")
                + f_mail("deleteditems", "Deleted Items")
                + f_mail("junkemail", "Junk Email")
                + f_mail("outbox", "Outbox")
                + f_mail("archive", "Archive")
                + "<t:ContactsFolder>"
                + '<t:FolderId Id="DF_contacts" ChangeKey="0"/>'
                + "<t:DisplayName>Contacts</t:DisplayName>"
                + "<t:FolderClass>IPF.Contact</t:FolderClass>"
                + '<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                + "</t:ContactsFolder>"
                + "<t:CalendarFolder>"
                + '<t:FolderId Id="DF_calendar" ChangeKey="0"/>'
                + "<t:DisplayName>Calendar</t:DisplayName>"
                + "<t:FolderClass>IPF.Appointment</t:FolderClass>"
                + '<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                + "</t:CalendarFolder>"
            )
            body = (
                f'<m:FindFolderResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:FindFolderResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f'<m:RootFolder TotalItemsInView="9" IncludesLastItemInRange="true">'
                f"<t:Folders>{folders_xml}</t:Folders>"
                f"</m:RootFolder>"
                f"</m:FindFolderResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:FindFolderResponse>"
            )
            resp = soap_envelope(body)
            log_ews("findfolder_response", {"bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "FindItem" in text:
            # Return last 10 emails owned by the authenticated user; if client requests IdOnly return ItemId only
            emails = (
                db.query(Email)
                .filter(Email.recipient_id == user.id)
                .order_by(Email.created_at.desc())
                .limit(10)
                .all()
            )
            wants_id_only = "<t:BaseShape>IdOnly</t:BaseShape>" in text
            # Determine target folder
            import re

            mfolder = re.search(r'<t:DistinguishedFolderId\s+Id="([^"]+)"', text)
            target = mfolder.group(1).lower() if mfolder else "inbox"
            if target == "contacts":
                from ..database import Contact

                contacts = (
                    db.query(Contact)
                    .filter(Contact.owner_id == user.id)
                    .limit(10)
                    .all()
                )
                if wants_id_only:
                    items_xml = "".join(
                        [
                            f'<t:Contact xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="CONTACT_{c.id}" ChangeKey="0"/></t:Contact>'
                            for c in contacts
                        ]
                    )
                else:
                    items_xml = "".join(
                        [
                            f'<t:Contact xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="CONTACT_{c.id}" ChangeKey="0"/><t:DisplayName>{(c.display_name or "").replace("&","&amp;")}</t:DisplayName><t:EmailAddresses><t:Entry Key="EmailAddress1">{(c.email_address_1 or "")}</t:Entry></t:EmailAddresses></t:Contact>'
                            for c in contacts
                        ]
                    )
            elif target == "calendar":
                from ..database import CalendarEvent

                events = (
                    db.query(CalendarEvent)
                    .filter(CalendarEvent.owner_id == user.id)
                    .order_by(CalendarEvent.start_time.desc())
                    .limit(10)
                    .all()
                )
                if wants_id_only:
                    items_xml = "".join(
                        [
                            f'<t:CalendarItem xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="CAL_{ev.id}" ChangeKey="0"/></t:CalendarItem>'
                            for ev in events
                        ]
                    )
                else:

                    def fmt(dt):
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""

                    items_xml = "".join(
                        [
                            f'<t:CalendarItem xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="CAL_{ev.id}" ChangeKey="0"/><t:Subject>{(ev.subject or "").replace("&","&amp;")}</t:Subject><t:Start>{fmt(ev.start_time)}</t:Start><t:End>{fmt(ev.end_time)}</t:End></t:CalendarItem>'
                            for ev in events
                        ]
                    )
            else:
                if wants_id_only:
                    items_xml = "".join(
                        [
                            f'<t:Message xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="ITEM_{e.id}" ChangeKey="0"/></t:Message>'
                            for e in emails
                        ]
                    )
                else:

                    def _has_atts(email_id: int) -> bool:
                        try:
                            return (
                                db.query(EmailAttachment)
                                .filter(EmailAttachment.email_id == email_id)
                                .count()
                                > 0
                            )
                        except Exception:
                            return False

                    items_xml = "".join(
                        [
                            (
                                f'<t:Message xmlns:t="{EWS_NS_TYPES}">'
                                f'<t:ItemId Id="ITEM_{e.id}" ChangeKey="0"/>'
                                f"<t:Subject>{(e.subject or '').replace('&','&amp;')}</t:Subject>"
                                f"<t:DateTimeReceived>{(e.created_at.strftime('%Y-%m-%dT%H:%M:%SZ') if getattr(e,'created_at',None) else '')}</t:DateTimeReceived>"
                                f"<t:ItemClass>IPM.Note</t:ItemClass>"
                                f"<t:IsRead>{'true' if getattr(e, 'is_read', True) else 'false'}</t:IsRead>"
                                f"<t:HasAttachments>{'true' if _has_atts(e.id) else 'false'}</t:HasAttachments>"
                                f'<t:ParentFolderId Id="DF_inbox" ChangeKey="0"/>'
                                f"<t:From><t:Mailbox><t:EmailAddress>{(getattr(e,'sender_email', None) or getattr(e, 'external_sender', '') or '').replace('&','&amp;')}</t:EmailAddress></t:Mailbox></t:From>"
                                f"</t:Message>"
                            )
                            for e in emails
                        ]
                    )
            if not items_xml:
                items_xml = ""
            body = (
                f'<m:FindItemResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:FindItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f'<m:RootFolder TotalItemsInView="{len(emails)}" IncludesLastItemInRange="true">'
                f"<t:Items>{items_xml}</t:Items>"
                f"</m:RootFolder>"
                f"</m:FindItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:FindItemResponse>"
            )
            resp = soap_envelope(body)
            log_ews("finditem_response", {"bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "Subscribe" in text and "StreamingSubscription" in text:
            # Minimal Streaming Subscribe: capture FolderIds and return SubscriptionId + Watermark
            import re

            folder_ids = re.findall(r'<t:FolderId[^>]*Id="([^"]+)"', text)
            sub = await ews_push_hub.subscribe(user.id, folder_ids)
            body = (
                f'<m:SubscribeResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:SubscribeResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:StreamingSubscriptionResponse>"
                f"<m:SubscriptionId>{sub.subscription_id}</m:SubscriptionId>"
                f"<m:Watermark>{sub.last_watermark}</m:Watermark>"
                f"</m:StreamingSubscriptionResponse>"
                f"</m:SubscribeResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:SubscribeResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetStreamingEvents" in text:
            # Long-poll up to ~30s for events; return any queued for the SubscriptionId
            import asyncio
            import re

            m = re.search(r"<m:SubscriptionId>([^<]+)</m:SubscriptionId>", text)
            sub_id = m.group(1) if m else ""
            sub = await ews_push_hub.get(sub_id)
            if not sub:
                body = (
                    f'<m:GetStreamingEventsResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                    f"<m:ResponseMessages>"
                    f'<m:GetStreamingEventsResponseMessageType ResponseClass="Success">'
                    f"<m:ResponseCode>NoError</m:ResponseCode>"
                    f"<m:Notifications/>"
                    f"</m:GetStreamingEventsResponseMessageType>"
                    f"</m:ResponseMessages>"
                    f"</m:GetStreamingEventsResponse>"
                )
                return Response(content=soap_envelope(body), media_type="text/xml")

            events = []
            try:
                # Wait briefly for at least one event
                evt = await asyncio.wait_for(sub.queue.get(), timeout=30.0)
                events.append(evt)
                # Drain any additional immediately available
                while True:
                    try:
                        events.append(sub.queue.get_nowait())
                    except Exception:
                        break
            except asyncio.TimeoutError:
                pass

            def notif_xml(evt: dict) -> str:
                return (
                    f"<m:Notification>"
                    f"<t:SubscriptionId>{sub.subscription_id}</t:SubscriptionId>"
                    f"<t:PreviousWatermark>{sub.last_watermark}</t:PreviousWatermark>"
                    f"<t:MoreEvents>false</t:MoreEvents>"
                    f"<t:NewMailEvent>"
                    f"<t:Watermark>{evt.get('watermark','')}</t:Watermark>"
                    f"<t:TimeStamp>{int(evt.get('time',0))}</t:TimeStamp>"
                    f"<t:FolderId Id=\"{evt.get('folder_id','DF_inbox')}\" ChangeKey=\"0\"/>"
                    f"<t:ItemId Id=\"ITEM_{evt.get('item_id',0)}\" ChangeKey=\"0\"/>"
                    f"</t:NewMailEvent>"
                    f"</m:Notification>"
                )

            notifications = "".join([notif_xml(e) for e in events])
            body = (
                f'<m:GetStreamingEventsResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:GetStreamingEventsResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Notifications>{notifications}</m:Notifications>"
                f"</m:GetStreamingEventsResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:GetStreamingEventsResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "Unsubscribe" in text:
            import re

            m = re.search(r"<m:SubscriptionId>([^<]+)</m:SubscriptionId>", text)
            sub_id = m.group(1) if m else ""
            await ews_push_hub.unsubscribe(sub_id)
            body = (
                f'<m:UnsubscribeResponse xmlns:m="{EWS_NS_MESSAGES}">'
                f"<m:ResponseMessages>"
                f'<m:UnsubscribeResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"</m:UnsubscribeResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:UnsubscribeResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetFolder" in text:
            # Minimal folder tree: return FolderId for requested distinguished folders
            import re

            requested_ids = re.findall(r"DistinguishedFolderId\s+Id=\"([^\"]+)\"", text)
            folder_ids = re.findall(r"FolderId\s+Id=\"(DF_[^\"]+)\"", text)
            requested_from_folder_ids = [fid[3:] for fid in folder_ids]
            all_ids = requested_ids + requested_from_folder_ids
            if not all_ids:
                all_ids = ["inbox"]
            display_map = {
                "msgfolderroot": "Root",
                "inbox": "Inbox",
                "deleteditems": "Deleted Items",
                "drafts": "Drafts",
                "outbox": "Outbox",
                "sentitems": "Sent Items",
                "junkemail": "Junk Email",
                "archive": "Archive",
                "contacts": "Contacts",
                "calendar": "Calendar",
            }

            def folder_xml(fid: str) -> str:
                name = display_map.get(fid, fid)
                if fid == "contacts":
                    return f'<t:ContactsFolder xmlns:t="{EWS_NS_TYPES}"><t:FolderId Id="DF_contacts" ChangeKey="0"/><t:ParentFolderId Id="DF_root" ChangeKey="0"/><t:FolderClass>IPF.Contact</t:FolderClass><t:DisplayName>{name}</t:DisplayName><t:TotalCount>0</t:TotalCount><t:ChildFolderCount>0</t:ChildFolderCount><t:UnreadCount>0</t:UnreadCount></t:ContactsFolder>'
                if fid == "calendar":
                    return f'<t:CalendarFolder xmlns:t="{EWS_NS_TYPES}"><t:FolderId Id="DF_calendar" ChangeKey="0"/><t:ParentFolderId Id="DF_root" ChangeKey="0"/><t:FolderClass>IPF.Appointment</t:FolderClass><t:DisplayName>{name}</t:DisplayName><t:TotalCount>0</t:TotalCount><t:ChildFolderCount>0</t:ChildFolderCount><t:UnreadCount>0</t:UnreadCount></t:CalendarFolder>'
                if fid == "msgfolderroot":
                    # Advertise accurate child count so clients show full tree
                    return f'<t:Folder><t:FolderId Id="DF_root" ChangeKey="0"/><t:DisplayName>{name}</t:DisplayName><t:ChildFolderCount>9</t:ChildFolderCount></t:Folder>'
                # add basic counts; compute inbox total from DB
                total = 0
                if fid == "inbox":
                    try:
                        total = (
                            db.query(Email)
                            .filter(Email.recipient_id == user.id)
                            .count()
                        )
                    except Exception:
                        total = 0
                elif fid == "sentitems":
                    try:
                        total = (
                            db.query(Email).filter(Email.sender_id == user.id).count()
                        )
                    except Exception:
                        total = 0
                return (
                    f"<t:Folder>"
                    f'<t:FolderId Id="DF_{fid}" ChangeKey="0"/>'
                    f'<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                    f"<t:FolderClass>IPF.Note</t:FolderClass>"
                    f"<t:DisplayName>{name}</t:DisplayName>"
                    f"<t:TotalCount>{total}</t:TotalCount>"
                    f"<t:ChildFolderCount>0</t:ChildFolderCount>"
                    f"<t:UnreadCount>0</t:UnreadCount>"
                    f"</t:Folder>"
                )

            # Per EWS, return one ResponseMessage per requested folder
            response_messages = "".join(
                [
                    (
                        f'<m:GetFolderResponseMessage ResponseClass="Success">'
                        f"<m:ResponseCode>NoError</m:ResponseCode>"
                        f"<m:Folders>{folder_xml(fid)}</m:Folders>"
                        f"</m:GetFolderResponseMessage>"
                    )
                    for fid in all_ids
                ]
            )
            body = (
                f'<m:GetFolderResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f"{response_messages}"
                f"</m:ResponseMessages>"
                f"</m:GetFolderResponse>"
            )
            resp = soap_envelope(body)
            log_ews("getfolder_response", {"bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "SyncFolderHierarchy" in text:
            # Return full default tree as "Create" changes with a static sync state
            def f_mail(fid: str, name: str) -> str:
                return (
                    f"<t:Create>"
                    f"<t:Folder>"
                    f'<t:FolderId Id="DF_{fid}" ChangeKey="0"/>'
                    f'<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                    f"<t:FolderClass>IPF.Note</t:FolderClass>"
                    f"<t:DisplayName>{name}</t:DisplayName>"
                    f"<t:TotalCount>0</t:TotalCount>"
                    f"<t:ChildFolderCount>0</t:ChildFolderCount>"
                    f"<t:UnreadCount>0</t:UnreadCount>"
                    f"</t:Folder>"
                    f"</t:Create>"
                )

            changes = (
                f_mail("inbox", "Inbox")
                + f_mail("drafts", "Drafts")
                + f_mail("sentitems", "Sent Items")
                + f_mail("deleteditems", "Deleted Items")
                + f_mail("junkemail", "Junk Email")
                + f_mail("outbox", "Outbox")
                + f_mail("archive", "Archive")
                + (
                    "<t:Create><t:ContactsFolder>"
                    + '<t:FolderId Id="DF_contacts" ChangeKey="0"/>'
                    + '<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                    + "<t:FolderClass>IPF.Contact</t:FolderClass>"
                    + "<t:DisplayName>Contacts</t:DisplayName>"
                    + "<t:TotalCount>0</t:TotalCount>"
                    + "<t:ChildFolderCount>0</t:ChildFolderCount>"
                    + "<t:UnreadCount>0</t:UnreadCount>"
                    + "</t:ContactsFolder></t:Create>"
                )
                + (
                    "<t:Create><t:CalendarFolder>"
                    + '<t:FolderId Id="DF_calendar" ChangeKey="0"/>'
                    + '<t:ParentFolderId Id="DF_root" ChangeKey="0"/>'
                    + "<t:FolderClass>IPF.Appointment</t:FolderClass>"
                    + "<t:DisplayName>Calendar</t:DisplayName>"
                    + "<t:TotalCount>0</t:TotalCount>"
                    + "<t:ChildFolderCount>0</t:ChildFolderCount>"
                    + "<t:UnreadCount>0</t:UnreadCount>"
                    + "</t:CalendarFolder></t:Create>"
                )
            )
            # If client sent SyncState, return empty Changes (already synced)
            import re

            has_state = re.search(r"<SyncState>(.*?)</SyncState>", text)
            sync_state = has_state.group(1) if has_state else "HIER_BASE_1"
            resp_changes = "" if has_state else changes
            body = (
                f'<m:SyncFolderHierarchyResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:SyncFolderHierarchyResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:SyncState>{sync_state}</m:SyncState>"
                f"<m:IncludesLastFolderInRange>true</m:IncludesLastFolderInRange>"
                f"<m:Changes>{resp_changes}</m:Changes>"
                f"</m:SyncFolderHierarchyResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:SyncFolderHierarchyResponse>"
            )
            resp = soap_envelope(body)
            log_ews("syncfolderhierarchy_response", {"bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "SyncFolderItems" in text:
            # Stateful delta sync per folder using last seen ITEM id watermark in SyncState
            import re

            # Target folder
            mfolder = re.search(r'<t:FolderId[^>]*Id="([^"]+)"', text)
            folder_id = mfolder.group(1) if mfolder else "DF_inbox"

            # Base query by folder semantics
            base_query = db.query(Email)
            if folder_id.endswith("sentitems") or folder_id == "DF_sentitems":
                base_query = base_query.filter(Email.sender_id == user.id)
            elif folder_id.endswith("deleteditems") or folder_id == "DF_deleteditems":
                base_query = base_query.filter(
                    Email.recipient_id == user.id, Email.is_deleted
                )
            else:
                base_query = base_query.filter(
                    Email.recipient_id == user.id, ~Email.is_deleted
                )

            # MaxChangesReturned (default 10)
            mmax = re.search(r"<MaxChangesReturned>(\d+)</MaxChangesReturned>", text)
            try:
                max_changes = int(mmax.group(1)) if mmax else 10
            except Exception:
                max_changes = 10
            if max_changes <= 0:
                max_changes = 10

            # Parse client SyncState watermark
            mstate = re.search(r"<SyncState>(.*?)</SyncState>", text)
            client_state = mstate.group(1) if mstate else None
            last_seen_id = 0
            if client_state and client_state.startswith("ITEMS_MAXID_"):
                try:
                    last_seen_id = int(client_state.split("_")[-1])
                except Exception:
                    last_seen_id = 0
            # Treat 'ITEMS_BASE_1' as baseline (no watermark)

            # Compute new items strictly newer than watermark
            new_items = (
                base_query.filter(Email.id > last_seen_id)
                .order_by(Email.id.asc())
                .limit(max_changes)
                .all()
            )

            # Build changes
            creates = "".join(
                [
                    (
                        f"<t:Create><t:Message>"
                        f'<t:ItemId Id="ITEM_{e.id}" ChangeKey="0"/>'
                        f'<t:ParentFolderId Id="{folder_id}" ChangeKey="0"/>'
                        f"</t:Message></t:Create>"
                    )
                    for e in new_items
                ]
            )

            # Advance watermark to newest id we have seen (either returned or current DB max)
            latest_id = last_seen_id
            if new_items:
                latest_id = max(last_seen_id, max(e.id for e in new_items))
            else:
                # No delta; keep existing watermark
                latest_id = last_seen_id

            # If no client_state (or baseline), initialize watermark to current folder max id
            if client_state is None or client_state == "ITEMS_BASE_1":
                try:
                    max_id_in_folder = (
                        base_query.order_by(Email.id.desc()).limit(1).first()
                    )
                    latest_id = max_id_in_folder.id if max_id_in_folder else latest_id
                except Exception:
                    pass

            new_sync_state = f"ITEMS_MAXID_{latest_id}"

            body = (
                f'<m:SyncFolderItemsResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:SyncFolderItemsResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:SyncState>{new_sync_state}</m:SyncState>"
                f"<m:IncludesLastItemInRange>true</m:IncludesLastItemInRange>"
                f"<m:Changes>{creates}</m:Changes>"
                f"</m:SyncFolderItemsResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:SyncFolderItemsResponse>"
            )
            resp = soap_envelope(body)
            log_ews(
                "syncfolderitems_response",
                {"count": len(new_items), "bytes": len(resp)},
            )
            return Response(content=resp, media_type="text/xml")
        if "GetItem" in text:
            # Return requested items mapped from DB for the authenticated user
            import re

            def iso(dt):
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""

            wants_mime = "<t:IncludeMimeContent>true</t:IncludeMimeContent>" in text
            email_ids = re.findall(r'<t:ItemId[^>]*Id="ITEM_(\d+)"', text)
            contact_ids = re.findall(r'<t:ItemId[^>]*Id="CONTACT_(\d+)"', text)
            cal_ids = re.findall(r'<t:ItemId[^>]*Id="CAL_(\d+)"', text)
            emails = (
                db.query(Email)
                .filter(
                    Email.recipient_id == user.id,
                    Email.id.in_([int(i) for i in email_ids] if email_ids else [-1]),
                )
                .all()
            )
            # Contacts
            contacts = []
            if contact_ids:
                try:
                    from ..database import Contact

                    contacts = (
                        db.query(Contact)
                        .filter(
                            Contact.owner_id == user.id,
                            Contact.id.in_([int(i) for i in contact_ids]),
                        )
                        .all()
                    )
                except Exception:
                    contacts = []
            # Calendar events
            events = []
            if cal_ids:
                try:
                    from ..database import CalendarEvent

                    events = (
                        db.query(CalendarEvent)
                        .filter(
                            CalendarEvent.owner_id == user.id,
                            CalendarEvent.id.in_([int(i) for i in cal_ids]),
                        )
                        .all()
                    )
                except Exception:
                    events = []

            def _attachments_xml(eid: int) -> str:
                try:
                    atts = (
                        db.query(EmailAttachment)
                        .filter(EmailAttachment.email_id == eid)
                        .all()
                    )
                except Exception:
                    atts = []
                if not atts:
                    return ""
                parts = []
                for a in atts:
                    parts.append(
                        "".join(
                            [
                                "<t:FileAttachment>",
                                f'<t:AttachmentId Id="ATT_{a.id}"/>',
                                f"<t:Name>{_xml(a.filename or 'attachment')}</t:Name>",
                                "</t:FileAttachment>",
                            ]
                        )
                    )
                return "<t:Attachments>" + "".join(parts) + "</t:Attachments>"

            email_items_xml = "".join(
                [
                    "".join(
                        [
                            f'<t:Message xmlns:t="{EWS_NS_TYPES}">',
                            f'<t:ItemId Id="ITEM_{e.id}" ChangeKey="0"/>',
                            f"<t:Subject>{_xml(getattr(e, 'subject', ''))}</t:Subject>",
                            f"<t:DateTimeSent>{iso(getattr(e, 'created_at', None))}</t:DateTimeSent>",
                            f"<t:DateTimeReceived>{iso(getattr(e, 'created_at', None))}</t:DateTimeReceived>",
                            "<t:ItemClass>IPM.Note</t:ItemClass>",
                            f"<t:Size>{getattr(e, 'size', 0) or 0}</t:Size>",
                            f"<t:From><t:Mailbox><t:EmailAddress>{_xml(getattr(e, 'sender_email', None) or getattr(e, 'external_sender', '') or '')}</t:EmailAddress></t:Mailbox></t:From>",
                            f"<t:Sender><t:Mailbox><t:EmailAddress>{_xml(getattr(e, 'sender_email', None) or getattr(e, 'external_sender', '') or '')}</t:EmailAddress></t:Mailbox></t:Sender>",
                            f"<t:ToRecipients><t:Mailbox><t:EmailAddress>{_xml(getattr(e, 'recipient_email', None) or getattr(e, 'external_recipient', '') or getattr(user,'email',''))}</t:EmailAddress></t:Mailbox></t:ToRecipients>",
                            f"<t:IsRead>{'true' if getattr(e, 'is_read', True) else 'false'}</t:IsRead>",
                            f"<t:HasAttachments>{'true' if db.query(EmailAttachment).filter(EmailAttachment.email_id == e.id).count() > 0 else 'false'}</t:HasAttachments>",
                            # Body omitted in this path to avoid nested f-string pitfalls; GetItem returns Body
                            f"<t:InternetMessageId>&lt;ITEM_{e.id}@local&gt;</t:InternetMessageId>",
                            (
                                (
                                    "<t:MimeContent>"
                                    + __import__("base64")
                                    .b64encode(
                                        (
                                            "MIME-Version: 1.0\r\n"
                                            + "Date: "
                                            + iso(getattr(e, "created_at", None))
                                            + "\r\n"
                                            + "From: "
                                            + (
                                                getattr(e, "sender_email", None)
                                                or getattr(e, "external_sender", "")
                                                or ""
                                            )
                                            + "\r\n"
                                            + "To: "
                                            + (
                                                getattr(e, "recipient_email", None)
                                                or getattr(e, "external_recipient", "")
                                                or getattr(user, "email", "")
                                            )
                                            + "\r\n"
                                            + "Subject: "
                                            + (getattr(e, "subject", "") or "")
                                            + "\r\n"
                                            + "Content-Type: "
                                            + (
                                                "text/html"
                                                if getattr(e, "body_html", None)
                                                else "text/plain"
                                            )
                                            + "; charset=utf-8\r\n"
                                            + "Content-Transfer-Encoding: 8bit\r\n\r\n"
                                            + (
                                                getattr(e, "body_html", None)
                                                if getattr(e, "body_html", None)
                                                else (getattr(e, "body", None) or "")
                                            )
                                        ).encode("utf-8")
                                    )
                                    .decode("ascii")
                                    + "</t:MimeContent>"
                                )
                                if wants_mime
                                else ""
                            ),
                            "<t:InternetMessageHeaders>",
                            '<t:InternetMessageHeader HeaderName="X-Server">365-Email-System</t:InternetMessageHeader>',
                            f"<t:InternetMessageHeader HeaderName=\"From\">{_xml(getattr(e, 'sender_email', None) or getattr(e, 'external_sender', '') or '')}</t:InternetMessageHeader>",
                            f"<t:InternetMessageHeader HeaderName=\"To\">{_xml(getattr(e, 'recipient_email', None) or getattr(e, 'external_recipient', '') or getattr(user,'email',''))}</t:InternetMessageHeader>",
                            f"<t:InternetMessageHeader HeaderName=\"Subject\">{_xml(getattr(e, 'subject', ''))}</t:InternetMessageHeader>",
                            "</t:InternetMessageHeaders>",
                            _attachments_xml(e.id),
                            "</t:Message>",
                        ]
                    )
                    for e in emails
                ]
            )
            contact_items_xml = "".join(
                [
                    "".join(
                        [
                            f'<t:Contact xmlns:t="{EWS_NS_TYPES}">',
                            f'<t:ItemId Id="CONTACT_{c.id}" ChangeKey="0"/>',
                            f"<t:DisplayName>{_xml(getattr(c,'display_name','') or '')}</t:DisplayName>",
                            "<t:EmailAddresses>",
                            f"<t:Entry Key=\"EmailAddress1\">{_xml(getattr(c,'email_address_1','') or '')}</t:Entry>",
                            "</t:EmailAddresses>",
                            "</t:Contact>",
                        ]
                    )
                    for c in contacts
                ]
            )
            cal_items_xml = "".join(
                [
                    "".join(
                        [
                            f'<t:CalendarItem xmlns:t="{EWS_NS_TYPES}">',
                            f'<t:ItemId Id="CAL_{ev.id}" ChangeKey="0"/>',
                            f"<t:Subject>{_xml(getattr(ev,'subject','') or '')}</t:Subject>",
                            f"<t:Start>{iso(getattr(ev,'start_time', None))}</t:Start>",
                            f"<t:End>{iso(getattr(ev,'end_time', None))}</t:End>",
                            "</t:CalendarItem>",
                        ]
                    )
                    for ev in events
                ]
            )
            items_xml = email_items_xml + contact_items_xml + cal_items_xml
            if not items_xml:
                items_xml = ""
            body = (
                f'<m:GetItemResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:GetItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Items>{items_xml}</m:Items>"
                f"</m:GetItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:GetItemResponse>"
            )
            resp = soap_envelope(body)
            log_ews("getitem_response", {"count": len(emails), "bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "ResolveNames" in text:
            # Search personal contacts first; fall back to echo of entry
            import re

            m = re.search(r"<UnresolvedEntry>([^<]+)</UnresolvedEntry>", text)
            entry = (m.group(1) if m else "").strip()
            resolutions = []
            try:
                from ..database import Contact

                if entry:
                    q = (
                        db.query(Contact)
                        .filter(Contact.owner_id == user.id)
                        .filter(
                            (Contact.display_name.ilike(f"%{entry}%"))
                            | (Contact.email_address_1.ilike(f"%{entry}%"))
                        )
                        .limit(5)
                        .all()
                    )
                    for c in q:
                        resolutions.append(
                            f"<t:Resolution><t:Mailbox><t:Name>{_xml(c.display_name or '')}</t:Name><t:EmailAddress>{_xml(c.email_address_1 or '')}</t:EmailAddress></t:Mailbox></t:Resolution>"
                        )
            except Exception:
                pass
            if not resolutions:
                # Fallback to echo
                resolutions.append(
                    f"<t:Resolution><t:Mailbox><t:EmailAddress>{_xml(entry or 'user@example.com')}</t:EmailAddress></t:Mailbox></t:Resolution>"
                )
            body = (
                f'<m:ResolveNamesResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:ResolveNamesResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:ResolutionSet>{''.join(resolutions)}</m:ResolutionSet>"
                f"</m:ResolveNamesResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:ResolveNamesResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "CreateItem" in text or "SendItem" in text:
            import asyncio
            import re
            from email.parser import Parser

            # Disposition: SendOnly, SaveOnly, SendAndSaveCopy
            mdisp = re.search(r'MessageDisposition="([^"]+)"', text)
            disposition = (mdisp.group(1).lower() if mdisp else "").strip()

            # Target folder for saved copy (default Sent Items)
            m_saved = re.search(
                r"<SavedItemFolderId>.*?<t:(?:FolderId|DistinguishedFolderId)[^>]*Id=\"([^\"]+)\"",
                text,
                re.S,
            )
            target_folder = m_saved.group(1) if m_saved else "sentitems"
            folder_xml_id = (
                target_folder
                if target_folder.startswith("DF_")
                else f"DF_{target_folder}"
            )
            log_ews(
                "createitem_start",
                {
                    "disposition": disposition,
                    "target_folder": target_folder,
                },
            )

            # Extract MimeContent
            mmime = re.search(r"<t:MimeContent>([\s\S]*?)</t:MimeContent>", text)
            new_item_xml = ""
            # queued_message_id kept for compatibility; value not used in response
            if disposition in ("saveonly", "sendandsavecopy") and mmime:
                try:
                    raw_b64 = mmime.group(1).strip()
                    raw_mime = base64.b64decode(raw_b64).decode(
                        "utf-8", errors="ignore"
                    )
                    msg = Parser().parsestr(raw_mime)
                    subj = msg.get("Subject", "")
                    to_addr = msg.get("To", "")
                    log_ews(
                        "createitem_parsed",
                        {
                            "subject": (subj or "")[:120],
                            "to": (to_addr or "")[:200],
                            "mime_len": len(raw_mime or ""),
                        },
                    )

                    body_text = ""
                    body_html = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            payload = part.get_payload(decode=True)
                            if (
                                ctype == "text/html"
                                and not body_html
                                and payload is not None
                            ):
                                body_html = payload.decode(errors="ignore")
                            if (
                                ctype == "text/plain"
                                and not body_text
                                and payload is not None
                            ):
                                body_text = payload.decode(errors="ignore")
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            body_text = payload.decode(errors="ignore")

                    email_row = Email(
                        subject=subj or "(no subject)",
                        body=body_text or None,
                        body_html=body_html or None,
                        mime_content=raw_mime,
                        mime_content_type=msg.get_content_type(),
                        sender_id=user.id,
                        recipient_id=None,
                        is_external=True,
                        external_recipient=to_addr,
                        external_sender=user.email,
                    )
                    db.add(email_row)
                    db.commit()
                    db.refresh(email_row)
                    log_ews(
                        "createitem_saved_copy",
                        {"item_id": email_row.id, "folder": folder_xml_id},
                    )
                    new_item_xml = (
                        f'<t:Message><t:ItemId Id="ITEM_{email_row.id}" ChangeKey="0"/>'
                        f'<t:ParentFolderId Id="{folder_xml_id}" ChangeKey="0"/></t:Message>'
                    )
                except Exception as e:
                    db.rollback()
                    log_ews("createitem_save_error", {"error": str(e)})

            # If the request asked to send, queue it for external delivery
            try:
                if (disposition in ("sendonly", "sendandsavecopy")) and mmime:
                    raw_b64 = mmime.group(1).strip()
                    raw_mime = base64.b64decode(raw_b64).decode(
                        "utf-8", errors="ignore"
                    )
                    msg = Parser().parsestr(raw_mime)
                    subj = msg.get("Subject", "")
                    to_addr = (msg.get("To", "") or "").split(",")[0].strip()
                    body_text = ""
                    body_html = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload is not None:
                                    body_text = payload.decode(errors="ignore")
                            if part.get_content_type() == "text/html":
                                payload = part.get_payload(decode=True)
                                if payload is not None:
                                    body_html = payload.decode(errors="ignore")
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            body_text = payload.decode(errors="ignore")

                    body_for_send = body_html or body_text or ""
                    log_ews("createitem_detected_html", {"has_html": bool(body_html)})
                    _ = email_delivery.queue_email(
                        sender_email=user.email,
                        recipient_email=to_addr,
                        subject=subj or "(no subject)",
                        body=body_for_send,
                    )
                    # Kick the delivery loop immediately (best-effort)
                    await email_delivery.process_queue(db)
                    log_ews("createitem_queue_processed", {})
            except Exception as e:
                log_ews("createitem_queue_error", {"error": str(e)})

            body = (
                f'<m:CreateItemResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:CreateItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Items>{new_item_xml}</m:Items>"
                f"</m:CreateItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:CreateItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "UpdateItem" in text:
            # Support setting IsRead true/false via SetItemField
            import re

            ids = re.findall(r'<t:ItemId[^>]*Id="ITEM_(\d+)"', text)
            is_read_match = re.search(r"<t:IsRead>(true|false)</t:IsRead>", text)
            set_is_read = None
            if is_read_match:
                set_is_read = True if is_read_match.group(1) == "true" else False
            updated_count = 0
            try:
                if ids and set_is_read is not None:
                    for sid in ids:
                        e = (
                            db.query(Email)
                            .filter(Email.id == int(sid), Email.recipient_id == user.id)
                            .first()
                        )
                        if e:
                            e.is_read = set_is_read
                            updated_count += 1
                    db.commit()
            except Exception:
                db.rollback()
            body = (
                f'<m:UpdateItemResponse xmlns:m="{EWS_NS_MESSAGES}">'
                f"<m:ResponseMessages>"
                f'<m:UpdateItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"</m:UpdateItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:UpdateItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "DeleteItem" in text:
            # Implement HardDelete / SoftDelete / MoveToDeletedItems
            import re

            delete_type_match = re.search(r'DeleteType="([^"]+)"', text)
            delete_type = (
                delete_type_match.group(1)
                if delete_type_match
                else "MoveToDeletedItems"
            ).lower()
            ids = re.findall(r'<t:ItemId[^>]*Id="ITEM_(\d+)"', text)
            try:
                for sid in ids:
                    email = (
                        db.query(Email)
                        .filter(Email.id == int(sid), Email.recipient_id == user.id)
                        .first()
                    )
                    if not email:
                        continue
                    if delete_type == "harddelete":
                        db.delete(email)
                    elif (
                        delete_type == "softdelete"
                        or delete_type == "movetodeleteditems"
                    ):
                        email.is_deleted = True
                db.commit()
            except Exception:
                db.rollback()
            body = (
                f'<m:DeleteItemResponse xmlns:m="{EWS_NS_MESSAGES}">'
                f"<m:ResponseMessages>"
                f'<m:DeleteItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"</m:DeleteItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:DeleteItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "MoveItem" in text:
            # Move to Deleted Items by toggling is_deleted flag
            import re

            to_folder_match = re.search(
                r'<t:(?:FolderId|DistinguishedFolderId)[^>]*Id="([^"]+)"', text
            )
            to_folder = to_folder_match.group(1) if to_folder_match else "deleteditems"
            ids = re.findall(r'<t:ItemId[^>]*Id="ITEM_(\d+)"', text)
            moved_xml = []
            try:
                for sid in ids:
                    email = (
                        db.query(Email)
                        .filter(Email.id == int(sid), Email.recipient_id == user.id)
                        .first()
                    )
                    if not email:
                        continue
                    if (
                        to_folder.endswith("deleteditems")
                        or to_folder == "DF_deleteditems"
                    ):
                        email.is_deleted = True
                    elif to_folder.endswith("inbox") or to_folder == "DF_inbox":
                        email.is_deleted = False
                    db.commit()
                    moved_xml.append(
                        f'<m:MovedItemId><t:ItemId Id="ITEM_{email.id}" ChangeKey="0"/></m:MovedItemId>'
                    )
            except Exception:
                db.rollback()
            body = (
                f'<m:MoveItemResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:MoveItemResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"{''.join(moved_xml)}"
                f"</m:MoveItemResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:MoveItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetAttachment" in text:
            # Return file content for requested AttachmentIds
            import os
            import re

            ids = re.findall(r'<t:AttachmentId[^>]*Id="ATT_(\d+)"', text)
            attachments = []
            for aid in ids:
                a = (
                    db.query(EmailAttachment)
                    .filter(EmailAttachment.id == int(aid))
                    .first()
                )
                if not a:
                    continue
                content_b64 = ""
                try:
                    with open(a.file_path, "rb") as f:
                        content_b64 = (
                            __import__("base64").b64encode(f.read()).decode("ascii")
                        )
                except Exception:
                    content_b64 = ""
                attachments.append(
                    "".join(
                        [
                            "<t:FileAttachment>",
                            f'<t:AttachmentId Id="ATT_{a.id}"/>',
                            f"<t:Name>{_xml(a.filename or 'attachment')}</t:Name>",
                            f"<t:Content>{content_b64}</t:Content>",
                            "</t:FileAttachment>",
                        ]
                    )
                )
            body = (
                f'<m:GetAttachmentResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:GetAttachmentResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Attachments>{''.join(attachments)}</m:Attachments>"
                f"</m:GetAttachmentResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:GetAttachmentResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "CreateAttachment" in text:
            # Save file attachment to disk and DB, link to target item
            import os
            import re

            mitem = re.search(r'<t:ParentItemId[^>]*Id="ITEM_(\d+)"', text)
            parent_id = int(mitem.group(1)) if mitem else None
            name_match = re.search(r"<t:Name>([\s\S]*?)</t:Name>", text)
            content_match = re.search(r"<t:Content>([\s\S]*?)</t:Content>", text)
            filename = name_match.group(1) if name_match else "attachment.bin"
            raw_b64 = content_match.group(1).strip() if content_match else ""
            saved_att_xml = []
            if parent_id and raw_b64:
                try:
                    data = __import__("base64").b64decode(raw_b64)
                    os.makedirs("data/attachments", exist_ok=True)
                    path = f"data/attachments/EMAIL_{parent_id}_{filename}"
                    with open(path, "wb") as f:
                        f.write(data)
                    att = EmailAttachment(
                        email_id=parent_id,
                        filename=filename,
                        content_type=None,
                        file_path=path,
                        file_size=len(data),
                    )
                    db.add(att)
                    db.commit()
                    db.refresh(att)
                    saved_att_xml.append(f'<m:AttachmentId Id="ATT_{att.id}"/>')
                except Exception:
                    db.rollback()
            body = (
                f'<m:CreateAttachmentResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:CreateAttachmentResponseMessageType ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"{''.join(saved_att_xml)}"
                f"</m:CreateAttachmentResponseMessageType>"
                f"</m:ResponseMessages>"
                f"</m:CreateAttachmentResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetUserAvailability" in text:
            body = (
                f'<m:GetUserAvailabilityResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:FreeBusyResponseArray/>"
                f"</m:GetUserAvailabilityResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        # Default minimal
        log_ews(
            "not_implemented",
            {
                "operation": operation_name,
                "preview": preview[:200],
            },
        )
        err = ews_error("NotImplemented")
        return Response(content=err, media_type="text/xml", status_code=200)
    except Exception as e:
        log_ews("exception", {"msg": str(e)})
        return Response(
            content=ews_error(str(e)), media_type="text/xml", status_code=500
        )
    finally:
        try:
            db.close()
        except Exception:
            pass
