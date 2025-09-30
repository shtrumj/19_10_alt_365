from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db, Email, User
from ..diagnostic_logger import log_ews

router = APIRouter(prefix="/EWS", tags=["ews"])

# Basic, minimal SOAP envelope helpers
EWS_NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
EWS_NS_TYPES = "http://schemas.microsoft.com/exchange/services/2006/types"
EWS_NS_MESSAGES = "http://schemas.microsoft.com/exchange/services/2006/messages"

def soap_envelope(body_xml: str) -> str:
    return f"""
<s:Envelope xmlns:s="{EWS_NS_SOAP}">
  <s:Body>
    {body_xml}
  </s:Body>
</s:Envelope>
""".strip()

def ews_error(message: str) -> str:
    inner = f"<m:ResponseCode xmlns:m=\"{EWS_NS_MESSAGES}\">ErrorInternalServerError</m:ResponseCode><m:MessageText xmlns:m=\"{EWS_NS_MESSAGES}\">{message}</m:MessageText>"
    return soap_envelope(f"<m:ResponseMessages xmlns:m=\"{EWS_NS_MESSAGES}\">{inner}</m:ResponseMessages>")

@router.get("/Exchange.asmx")
@router.post("/Exchange.asmx")
async def ews_aspx(request: Request, db: Session = Depends(get_db)):
    """Very minimal EWS endpoint to make Outlook probe pass. Supports FindItem on Inbox with a tiny response.
    This is not a full EWS; it only returns a small item list mapped from DB.
    """
    try:
        raw = await request.body()
        ua = request.headers.get("User-Agent")
        log_ews("request", {
            "ua": ua,
            "preview": raw.decode('utf-8', errors='ignore')[:1000],
        })

        text = raw.decode('utf-8', errors='ignore')
        # Naive routing based on method names in SOAP
        if "FindItem" in text:
            # Return last 10 emails as items
            emails = db.query(Email).order_by(Email.created_at.desc()).limit(10).all()
            items_xml = "".join([
                f"<t:Message xmlns:t=\"{EWS_NS_TYPES}\"><t:Subject>{(e.subject or '').replace('&','&amp;')}</t:Subject></t:Message>"
                for e in emails
            ])
            body = f"<m:FindItemResponse xmlns:m=\"{EWS_NS_MESSAGES}\" xmlns:t=\"{EWS_NS_TYPES}\"><m:ResponseMessages><m:FindItemResponseMessage><m:RootFolder><t:Items>{items_xml}</t:Items></m:RootFolder></m:FindItemResponseMessage></m:ResponseMessages></m:FindItemResponse>"
            resp = soap_envelope(body)
            log_ews("finditem_response", {"bytes": len(resp)})
            return Response(content=resp, media_type="text/xml")
        if "GetFolder" in text:
            # Minimal folder tree (Inbox only)
            body = f"<m:GetFolderResponse xmlns:m=\"{EWS_NS_MESSAGES}\" xmlns:t=\"{EWS_NS_TYPES}\"><m:ResponseMessages><m:GetFolderResponseMessage><m:Folders><t:Folder><t:DisplayName>Inbox</t:DisplayName></t:Folder></m:Folders></m:GetFolderResponseMessage></m:ResponseMessages></m:GetFolderResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetItem" in text:
            # Return a single dummy item with body preview
            email = db.query(Email).order_by(Email.created_at.desc()).first()
            subj = (email.subject if email else "(no subject)").replace('&','&amp;')
            body_txt = (email.body if (email and email.body) else "").replace('&','&amp;')
            body = f"<m:GetItemResponse xmlns:m=\"{EWS_NS_MESSAGES}\" xmlns:t=\"{EWS_NS_TYPES}\"><m:ResponseMessages><m:GetItemResponseMessage><m:Items><t:Message><t:Subject>{subj}</t:Subject><t:Body BodyType=\"Text\">{body_txt[:512]}</t:Body></t:Message></m:Items></m:GetItemResponseMessage></m:ResponseMessages></m:GetItemResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "ResolveNames" in text:
            # Echo back an email address from request if found
            import re
            m = re.search(r"<UnresolvedEntry>([^<]+)</UnresolvedEntry>", text)
            entry = (m.group(1) if m else "user@example.com")
            body = f"<m:ResolveNamesResponse xmlns:m=\"{EWS_NS_MESSAGES}\" xmlns:t=\"{EWS_NS_TYPES}\"><m:ResponseMessages><m:ResolveNamesResponseMessage><m:ResolutionSet><t:Resolution><t:Mailbox><t:EmailAddress>{entry}</t:EmailAddress></t:Mailbox></t:Resolution></m:ResolutionSet></m:ResolveNamesResponseMessage></m:ResponseMessages></m:ResolveNamesResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "CreateItem" in text or "SendItem" in text:
            # Acknowledge success; real send is future work
            body = f"<m:CreateItemResponse xmlns:m=\"{EWS_NS_MESSAGES}\"><m:ResponseMessages><m:CreateItemResponseMessage><m:Items/></m:CreateItemResponseMessage></m:ResponseMessages></m:CreateItemResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "UpdateItem" in text:
            body = f"<m:UpdateItemResponse xmlns:m=\"{EWS_NS_MESSAGES}\"><m:ResponseMessages><m:UpdateItemResponseMessage/></m:ResponseMessages></m:UpdateItemResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "DeleteItem" in text:
            body = f"<m:DeleteItemResponse xmlns:m=\"{EWS_NS_MESSAGES}\"><m:ResponseMessages><m:DeleteItemResponseMessage/></m:ResponseMessages></m:DeleteItemResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        if "GetUserAvailability" in text:
            body = f"<m:GetUserAvailabilityResponse xmlns:m=\"{EWS_NS_MESSAGES}\" xmlns:t=\"{EWS_NS_TYPES}\"><m:FreeBusyResponseArray/></m:GetUserAvailabilityResponse>"
            return Response(content=soap_envelope(body), media_type="text/xml")
        # Default minimal
        err = ews_error("NotImplemented")
        log_ews("not_implemented", {})
        return Response(content=err, media_type="text/xml", status_code=200)
    except Exception as e:
        log_ews("exception", {"msg": str(e)})
        return Response(content=ews_error(str(e)), media_type="text/xml", status_code=500)


