import base64

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import authenticate_user
from ..database import Email, User, get_db
from ..diagnostic_logger import log_ews

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
async def ews_aspx(request: Request, db: Session = Depends(get_db)):
    """Very minimal EWS endpoint to make Outlook probe pass. Supports FindItem on Inbox with a tiny response.
    This is not a full EWS; it only returns a small item list mapped from DB.
    """
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
        log_ews(
            "request",
            {
                "ua": ua,
                "preview": raw.decode("utf-8", errors="ignore")[:1000],
            },
        )

        text = raw.decode("utf-8", errors="ignore")
        # Naive routing based on method names in SOAP
        if "FindFolder" in text or "<m:FindFolder" in text:
            # Enumerate key folders under root, including Contacts and Calendar
            folders_xml = (
                f'<t:ContactsFolder xmlns:t="{EWS_NS_TYPES}">'
                f'<t:FolderId Id="DF_contacts" ChangeKey="0"/>'
                f"<t:DisplayName>Contacts</t:DisplayName>"
                f"</t:ContactsFolder>"
                f'<t:CalendarFolder xmlns:t="{EWS_NS_TYPES}">'
                f'<t:FolderId Id="DF_calendar" ChangeKey="0"/>'
                f"<t:DisplayName>Calendar</t:DisplayName>"
                f"</t:CalendarFolder>"
            )
            body = (
                f'<m:FindFolderResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:FindFolderResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f'<m:RootFolder TotalItemsInView="2" IncludesLastItemInRange="true">'
                f"<t:Folders>{folders_xml}</t:Folders>"
                f"</m:RootFolder>"
                f"</m:FindFolderResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:FindFolderResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "FindItem" in text:
            # Return last 10 emails as items; if client requests IdOnly return ItemId only
            emails = db.query(Email).order_by(Email.created_at.desc()).limit(10).all()
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
                    items_xml = "".join(
                        [
                            f'<t:Message xmlns:t="{EWS_NS_TYPES}"><t:ItemId Id="ITEM_{e.id}" ChangeKey="0"/><t:Subject>{(e.subject or "").replace("&","&amp;")}</t:Subject></t:Message>'
                            for e in emails
                        ]
                    )
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
        if "GetFolder" in text:
            # Minimal folder tree: return FolderId for requested distinguished folders
            import re

            requested_ids = re.findall(r"DistinguishedFolderId\s+Id=\"([^\"]+)\"", text)
            if not requested_ids:
                requested_ids = ["inbox"]
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
                    return f'<t:ContactsFolder xmlns:t="{EWS_NS_TYPES}"><t:FolderId Id="DF_contacts" ChangeKey="0"/><t:DisplayName>{name}</t:DisplayName><t:FolderClass>IPF.Contact</t:FolderClass></t:ContactsFolder>'
                if fid == "calendar":
                    return f'<t:CalendarFolder xmlns:t="{EWS_NS_TYPES}"><t:FolderId Id="DF_calendar" ChangeKey="0"/><t:DisplayName>{name}</t:DisplayName><t:FolderClass>IPF.Appointment</t:FolderClass></t:CalendarFolder>'
                if fid == "msgfolderroot":
                    # Advertise child count so clients attempt discovery
                    return f'<t:Folder><t:FolderId Id="DF_root" ChangeKey="0"/><t:DisplayName>{name}</t:DisplayName><t:ChildFolderCount>2</t:ChildFolderCount></t:Folder>'
                return f'<t:Folder><t:FolderId Id="DF_{fid}" ChangeKey="0"/><t:DisplayName>{name}</t:DisplayName></t:Folder>'

            folders_xml = "".join([folder_xml(fid) for fid in requested_ids])
            body = (
                f'<m:GetFolderResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:GetFolderResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Folders>{folders_xml}</m:Folders>"
                f"</m:GetFolderResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:GetFolderResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetItem" in text:
            # Return a single dummy item with body preview
            email = db.query(Email).order_by(Email.created_at.desc()).first()
            subj = (email.subject if email else "(no subject)").replace("&", "&amp;")
            body_txt = (email.body if (email and email.body) else "").replace(
                "&", "&amp;"
            )
            body = (
                f'<m:GetItemResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:GetItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f'<m:Items><t:Message><t:Subject>{subj}</t:Subject><t:Body BodyType="Text">{body_txt[:512]}</t:Body></t:Message></m:Items>'
                f"</m:GetItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:GetItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "ResolveNames" in text:
            # Echo back an email address from request if found
            import re

            m = re.search(r"<UnresolvedEntry>([^<]+)</UnresolvedEntry>", text)
            entry = m.group(1) if m else "user@example.com"
            body = (
                f'<m:ResolveNamesResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:ResponseMessages>"
                f'<m:ResolveNamesResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:ResolutionSet><t:Resolution><t:Mailbox><t:EmailAddress>{entry}</t:EmailAddress></t:Mailbox></t:Resolution></m:ResolutionSet>"
                f"</m:ResolveNamesResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:ResolveNamesResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "CreateItem" in text or "SendItem" in text:
            # Acknowledge success; real send is future work
            body = (
                f'<m:CreateItemResponse xmlns:m="{EWS_NS_MESSAGES}">'
                f"<m:ResponseMessages>"
                f'<m:CreateItemResponseMessage ResponseClass="Success">'
                f"<m:ResponseCode>NoError</m:ResponseCode>"
                f"<m:Items/>"
                f"</m:CreateItemResponseMessage>"
                f"</m:ResponseMessages>"
                f"</m:CreateItemResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "UpdateItem" in text:
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
        if "GetUserAvailability" in text:
            body = (
                f'<m:GetUserAvailabilityResponse xmlns:m="{EWS_NS_MESSAGES}" xmlns:t="{EWS_NS_TYPES}">'
                f"<m:FreeBusyResponseArray/>"
                f"</m:GetUserAvailabilityResponse>"
            )
            return Response(content=soap_envelope(body), media_type="text/xml")
        # Default minimal
        err = ews_error("NotImplemented")
        log_ews("not_implemented", {})
        return Response(content=err, media_type="text/xml", status_code=200)
    except Exception as e:
        log_ews("exception", {"msg": str(e)})
        return Response(
            content=ews_error(str(e)), media_type="text/xml", status_code=500
        )
