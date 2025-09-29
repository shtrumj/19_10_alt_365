from fastapi import APIRouter, Request
from fastapi.responses import Response
from ..config import settings
from ..database import SessionLocal, User
import logging
import uuid
from ..diagnostic_logger import (
    log_autodiscover, outlook_diagnostics, log_autodiscover_request,
    log_outlook_connection_issue
)

router = APIRouter()

@router.post("/Autodiscover/Autodiscover.xml")
async def autodiscover(request: Request):
    """ActiveSync-compatible autodiscover response (Outlook/Exchange style)."""
    logger = logging.getLogger(__name__)
    host = settings.HOSTNAME or request.headers.get("Host", "")
    mobilesync_url = f"https://{host}/activesync/Microsoft-Server-ActiveSync"
    
    # Enhanced diagnostic logging
    request_id = str(uuid.uuid4())
    user_agent = request.headers.get("User-Agent", "")
    
    # Try to extract email/UPN from request body if present
    body = await request.body()
    try:
        logger.info("Autodiscover POST from %s UA=%s", request.client.host if request.client else "?", user_agent)
        logger.debug("Autodiscover body: %s", body.decode('utf-8', errors='ignore')[:2000])
        
        # Log this as an Outlook phase
        outlook_diagnostics.log_outlook_phase("autodiscover_xml_request", {
            "request_id": request_id,
            "host": host,
            "user_agent": user_agent,
            "client_ip": request.client.host if request.client else "unknown",
            "content_length": len(body)
        })
        log_autodiscover("request", {
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
            "content_type": request.headers.get("Content-Type"),
            "content_length": request.headers.get("Content-Length"),
            "preview": body.decode('utf-8', errors='ignore')[:1000],
        })
    except Exception:
        pass
    requested_email = None
    try:
        text = body.decode('utf-8', errors='ignore')
        # Very simple extraction: <EMailAddress>user@domain</EMailAddress>
        import re
        m = re.search(r"<EMailAddress>([^<]+)</EMailAddress>", text, re.I)
        if m:
            requested_email = m.group(1)
            
        # Check if this is a 2006a schema request (Outlook sometimes adds 'a' suffix)
        is_2006a_request = "2006a" in text
        if is_2006a_request:
            logger.info("Received 2006a schema request from Outlook")
    except Exception:
        pass

    display_name = "365 Email User"
    if requested_email:
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.email == requested_email).first()
            if user:
                display_name = user.full_name or user.username or requested_email
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass

    # Build Exchange/Outlook-style response schema with proper EXCH protocol elements
    owa_url = f"https://{host}/owa"
    ews_url = f"https://{host}/EWS/Exchange.asmx"
    exch_server = host
    mapi_server_url = f"https://{host}/mapi/emsmdb"  # Full MAPI endpoint URL
    
    # Extract domain from email for MdbDN
    domain = requested_email.split('@')[1] if requested_email and '@' in requested_email else host
    user_part = requested_email.split('@')[0] if requested_email and '@' in requested_email else 'user'
    
    xml = f"""
<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response>
    <ErrorCode>NoError</ErrorCode>
    <User>
      <DisplayName>{display_name}</DisplayName>
      <EMailAddress>{requested_email or ('user@' + host)}</EMailAddress>
    </User>
    <Account>
      <AccountType>Exchange</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>EXCH</Type>
        <Server>{exch_server}</Server>
        <Port>443</Port>
        <SSL>On</SSL>
        <AuthPackage>Ntlm</AuthPackage>
        <MdbDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Configuration/cn=Servers/cn={exch_server}/cn=Microsoft Private MDB</MdbDN>
        <MailboxDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Recipients/cn={user_part}</MailboxDN>
        <ServerDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Configuration/cn=Servers/cn={exch_server}</ServerDN>
        <ServerVersion>15.01.2507.027</ServerVersion>
        <AD>owa.shtrum.com</AD>
        <EwsUrl>{ews_url}</EwsUrl>
        <EcpUrl>{owa_url}</EcpUrl>
        <Internal>
          <Url>{mapi_server_url}</Url>
          <EwsUrl>{ews_url}</EwsUrl>
          <OOFUrl>{owa_url}/oof</OOFUrl>
          <UMUrl>{owa_url}/um</UMUrl>
          <OABUrl>https://{host}/oab/oab.xml</OABUrl>
        </Internal>
        <External>
          <Url>{mapi_server_url}</Url>
          <EwsUrl>{ews_url}</EwsUrl>
          <OOFUrl>{owa_url}/oof</OOFUrl>
          <UMUrl>{owa_url}/um</UMUrl>
          <OABUrl>https://{host}/oab/oab.xml</OABUrl>
        </External>
      </Protocol>
      <Protocol>
        <Type>EXPR</Type>
        <Server>{exch_server}</Server>
        <Port>443</Port>
        <SSL>On</SSL>
        <AuthPackage>Basic</AuthPackage>
        <EwsUrl>{ews_url}</EwsUrl>
        <External>
          <Url>{mapi_server_url}</Url>
        </External>
      </Protocol>
      <Protocol>
        <Type>WEB</Type>
        <OWAUrl>{owa_url}</OWAUrl>
        <SSL>On</SSL>
      </Protocol>
      <Protocol>
        <Type>IMAP</Type>
        <Server>{host}</Server>
        <Port>993</Port>
        <SSL>On</SSL>
        <AuthPackage>Basic</AuthPackage>
      </Protocol>
      <Protocol>
        <Type>SMTP</Type>
        <Server>{host}</Server>
        <Port>587</Port>
        <SSL>On</SSL>
        <AuthPackage>Basic</AuthPackage>
      </Protocol>
    </Account>
  </Response>
</Autodiscover>
""".strip()
    try:
        logger.debug("Autodiscover response XML: %s", xml)
        log_autodiscover("response", {"xml_preview": xml[:1000]})
    except Exception:
        pass
    return Response(content=xml, media_type="application/xml")

# Lowercase alias
@router.post("/autodiscover/autodiscover.xml")
async def autodiscover_lower(request: Request):
    return await autodiscover(request)

# Helpful GET handler for browsers/tools (Outlook uses POST)
@router.get("/Autodiscover/Autodiscover.xml")
async def autodiscover_get(request: Request):
    host = settings.HOSTNAME or request.headers.get("Host", "")
    mobilesync_url = f"https://{host}/activesync/Microsoft-Server-ActiveSync"
    # Log GET hits as well (browsers, some clients probe with GET)
    try:
        log_autodiscover("get", {
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        })
    except Exception:
        pass
    owa_url = f"https://{host}/owa"
    xml = f"""
<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response>
    <ErrorCode>NoError</ErrorCode>
    <User>
      <DisplayName>Unknown</DisplayName>
      <EMailAddress>unknown@{host}</EMailAddress>
    </User>
    <Account>
      <AccountType>Exchange</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>EXCH</Type>
        <Server>{host}</Server>
        <Port>443</Port>
        <SSL>On</SSL>
        <AuthPackage>Ntlm</AuthPackage>
        <External>
          <Url>{mobilesync_url}</Url>
        </External>
      </Protocol>
      <Protocol>
        <Type>WEB</Type>
        <OWAUrl>{owa_url}</OWAUrl>
        <SSL>On</SSL>
      </Protocol>
    </Account>
  </Response>
</Autodiscover>
""".strip()
    return Response(content=xml, media_type="application/xml")

@router.get("/autodiscover/autodiscover.xml")
async def autodiscover_get_lower(request: Request):
    return await autodiscover_get(request)

# JSON Autodiscover endpoint for modern Outlook clients
@router.get("/autodiscover/autodiscover.json/v1.0/{email_address}")
async def autodiscover_json(email_address: str, request: Request):
    """JSON-based Autodiscover for modern Outlook clients"""
    try:
        host = settings.HOSTNAME or request.headers.get("Host", "")
        
        # Log the JSON autodiscover request
        log_autodiscover("json_request", {
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
            "email": email_address,
            "protocol": request.url.query
        })
        
        # Get user info
        display_name = "365 Email User"
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.email == email_address).first()
            if user:
                display_name = user.full_name or user.username or email_address
        except Exception:
            pass
        finally:
            try:
                db.close()
            except:
                pass
        
        # Build JSON response compatible with Office 365/Exchange Online format
        json_response = {
            "Protocol": "Exchange",
            "Url": f"https://{host}",
            "AuthPackage": "Ntlm", 
            "ServerExclusiveConnect": False,
            "CertPrincipalName": host,
            "GroupingInformation": "Exchange",
            "EwsUrl": f"https://{host}/EWS/Exchange.asmx",
            "EcpUrl": f"https://{host}/owa",
            "OOFUrl": f"https://{host}/owa/oof",
            "UMUrl": f"https://{host}/owa/um"
        }
        
        log_autodiscover("json_response", {"email": email_address, "protocol": "Exchange"})
        
        return json_response
        
    except Exception as e:
        logger.error(f"Error in JSON autodiscover: {e}")
        # Return error response
        return {"error": "AutodiscoverFailed", "message": "Unable to retrieve settings"}

@router.get("/autodiscover/autodiscover.json/v1.0/{email_address:path}")
async def autodiscover_json_with_params(email_address: str, request: Request):
    """Handle JSON autodiscover with query parameters"""
    # Extract just the email part if there are query parameters
    email_only = email_address.split('?')[0] if '?' in email_address else email_address
    return await autodiscover_json(email_only, request)


