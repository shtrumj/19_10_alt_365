from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, RedirectResponse
from ..config import settings
from ..database import SessionLocal, User
import html
import logging
import uuid
from ..diagnostic_logger import (
    log_autodiscover, outlook_diagnostics, log_autodiscover_request,
    log_outlook_connection_issue, log_outlook_health
)

router = APIRouter()

@router.get("/Autodiscover/Autodiscover.xml")
@router.post("/Autodiscover/Autodiscover.xml")
async def autodiscover(request: Request):
    """ActiveSync-compatible autodiscover response (Outlook/Exchange style)."""
    logger = logging.getLogger(__name__)
    host = settings.HOSTNAME or request.headers.get("Host", "")
    
    # Enhanced diagnostic logging
    request_id = str(uuid.uuid4())
    user_agent = request.headers.get("User-Agent", "")
    
    # Try to extract email/UPN from request body if present
    body = await request.body()
    try:
        logger.info("Autodiscover POST from %s UA=%s", request.client.host if request.client else "?", user_agent)
        logger.debug("Autodiscover body: %s", body.decode('utf-8', errors='ignore')[:2000])
        
        # Log this as an Outlook phase with health monitoring
        client_ip = request.client.host if request.client else "unknown"
        
        # Enhanced health monitoring
        log_outlook_health("autodiscover_request", client_ip, user_agent, {
            "host": host,
            "content_length": len(body),
            "is_outlook": "outlook" in user_agent.lower(),
            "request_id": request_id
        })
        
        outlook_diagnostics.log_outlook_phase("autodiscover_xml_request", {
            "request_id": request_id,
            "host": host,
            "user_agent": user_agent,
            "client_ip": client_ip,
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
    response_schema = "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006"
    requested_email = None
    try:
        text = body.decode('utf-8', errors='ignore')
        # Very simple extraction: <EMailAddress>user@domain</EMailAddress>
        import re
        m = re.search(r"<EMailAddress>([^<]+)</EMailAddress>", text, re.I)
        if m:
            requested_email = m.group(1).strip()

        # Preferred response schema if supplied
        schema_match = re.search(r"<AcceptableResponseSchema>([^<]+)</AcceptableResponseSchema>", text, re.I)
        if schema_match:
            schema_value = schema_match.group(1).strip()
            if schema_value.endswith("/2006a"):
                response_schema = "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"
        if "2006a" in text and not schema_match:
            response_schema = "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"
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

    # Build protocol URLs
    owa_url = f"https://{host}/owa/"
    ews_url = f"https://{host}/EWS/Exchange.asmx"
    activesync_url = f"https://{host}/Microsoft-Server-ActiveSync"
    mapi_url = f"https://{host}/mapi/emsmdb"
    oab_url = f"https://{host}/oab/default.oab"

    effective_email = requested_email or f"user@{host}"
    escaped_display = html.escape(display_name)
    escaped_email = html.escape(effective_email)
    escaped_host = html.escape(host)
    escaped_owa = html.escape(owa_url)
    escaped_ews = html.escape(ews_url)
    escaped_as = html.escape(activesync_url)
    escaped_mapi = html.escape(mapi_url)
    escaped_oab = html.escape(oab_url)

    response_ns = response_schema

    xml = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Response xmlns="{response_ns}">
    <ErrorCode>NoError</ErrorCode>
    <User>
      <DisplayName>{escaped_display}</DisplayName>
      <EMailAddress>{escaped_email}</EMailAddress>
    </User>
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>EXCH</Type>
        <Server>{escaped_host}</Server>
        <Port>443</Port>
        <ServerVersion>15.01.2507.000</ServerVersion>
        <SSL>On</SSL>
        <AuthPackage>Negotiate</AuthPackage>
        <LoginName>{escaped_email}</LoginName>
        <ASUrl>{escaped_as}</ASUrl>
        <EwsUrl>{escaped_ews}</EwsUrl>
        <OOFUrl>{escaped_ews}</OOFUrl>
        <OABUrl>{escaped_oab}</OABUrl>
        <CertPrincipalName>msstd:{escaped_host}</CertPrincipalName>
        <PublicFolderServer>{escaped_host}</PublicFolderServer>
        <ActiveDirectoryServer>{escaped_host}</ActiveDirectoryServer>
        <MapiHttpEnabled>true</MapiHttpEnabled>
        <MapiHttpServerUrl>{escaped_mapi}</MapiHttpServerUrl>
        <MapiHttpVersion>2</MapiHttpVersion>
        <ServerExclusiveConnect>On</ServerExclusiveConnect>
        <Internal>
          <Server>{escaped_host}</Server>
          <Url>{escaped_mapi}</Url>
          <ASUrl>{escaped_as}</ASUrl>
          <EwsUrl>{escaped_ews}</EwsUrl>
          <OOFUrl>{escaped_ews}</OOFUrl>
          <CertPrincipalName>msstd:{escaped_host}</CertPrincipalName>
        </Internal>
        <External>
          <Server>{escaped_host}</Server>
          <Url>{escaped_mapi}</Url>
          <ASUrl>{escaped_as}</ASUrl>
          <EwsUrl>{escaped_ews}</EwsUrl>
          <OOFUrl>{escaped_ews}</OOFUrl>
          <CertPrincipalName>msstd:{escaped_host}</CertPrincipalName>
        </External>
      </Protocol>
      <Protocol>
        <Type>EXPR</Type>
        <Server>{escaped_host}</Server>
        <SSL>On</SSL>
        <AuthPackage>Basic</AuthPackage>
        <LoginName>{escaped_email}</LoginName>
        <ASUrl>{escaped_as}</ASUrl>
        <EwsUrl>{escaped_ews}</EwsUrl>
        <OOFUrl>{escaped_ews}</OOFUrl>
        <OABUrl>{escaped_oab}</OABUrl>
        <CertPrincipalName>msstd:{escaped_host}</CertPrincipalName>
      </Protocol>
      <Protocol>
        <Type>WEB</Type>
        <OWAUrl>{escaped_owa}</OWAUrl>
        <OWAUrlAuth>Basic</OWAUrlAuth>
        <OOFUrl>{escaped_owa}?path=/options/automaticreply</OOFUrl>
        <UMUrl>{escaped_owa}?path=/options/callanswering</UMUrl>
        <SSL>On</SSL>
      </Protocol>
      <Protocol>
        <Type>MobileSync</Type>
        <Server>{escaped_host}</Server>
        <SSL>On</SSL>
        <AuthRequired>On</AuthRequired>
        <UserName>{escaped_email}</UserName>
        <DomainRequired>Off</DomainRequired>
        <LoginName>{escaped_email}</LoginName>
        <PasswordRequired>On</PasswordRequired>
        <InternalUrl>{escaped_as}</InternalUrl>
        <ExternalUrl>{escaped_as}</ExternalUrl>
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

# FIXED: Removed duplicate route definition - the main autodiscover function already handles both GET and POST

@router.get("/autodiscover/autodiscover.xml")
async def autodiscover_get_lower(request: Request):
    return await autodiscover(request)

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
        
        activesync_url = f"https://{host}/Microsoft-Server-ActiveSync"
        ews_url = f"https://{host}/EWS/Exchange.asmx"
        mapi_url = f"https://{host}/mapi/emsmdb"

        log_autodiscover("json_response", {
            "email": email_address,
            "reason": "Providing JSON autodiscover response for Outlook compatibility",
            "ua": request.headers.get("User-Agent", "")
        })

        json_response = {
            "User": {
                "DisplayName": display_name,
                "EmailAddress": email_address
            },
            "Account": {
                "AccountType": "email",
                "Action": "settings",
                "UserName": email_address
            },
            "Protocol": [
                {
                    "Type": "EXCH",
                    "Server": host,
                    "SSL": "On",
                    "AuthPackage": "Negotiate",
                    "ASUrl": activesync_url,
                    "EwsUrl": ews_url,
                    "OOFUrl": ews_url,
                    "OABUrl": f"https://{host}/oab/default.oab",
                    "LoginName": email_address,
                    "MapiHttpEnabled": True,
                    "MapiHttpServerUrl": mapi_url,
                    "MapiHttpVersion": "2",
                    "ServerExclusiveConnect": True,
                    "PublicFolderServer": host,
                    "ActiveDirectoryServer": host,
                    "CertPrincipalName": f"msstd:{host}"
                },
                {
                    "Type": "EXPR",
                    "Server": host,
                    "SSL": "On",
                    "AuthPackage": "Basic",
                    "ASUrl": activesync_url,
                    "EwsUrl": ews_url,
                    "OOFUrl": ews_url,
                    "OABUrl": f"https://{host}/oab/default.oab",
                    "LoginName": email_address,
                    "CertPrincipalName": f"msstd:{host}"
                },
                {
                    "Type": "MobileSync",
                    "Server": host,
                    "Url": activesync_url,
                    "SSL": "On",
                    "AuthPackage": "Basic",
                    "LoginName": email_address
                },
                {
                    "Type": "WEB",
                    "OWAUrl": f"https://{host}/owa/",
                    "OOFUrl": f"https://{host}/owa/?path=/options/automaticreply"
                }
            ]
        }
        
        return json_response
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in JSON autodiscover: {e}")
        # Return error response
        return {"error": "AutodiscoverFailed", "message": "Unable to retrieve settings"}

@router.get("/autodiscover/autodiscover.json/v1.0/{email_address:path}")
async def autodiscover_json_with_params(email_address: str, request: Request):
    """Handle JSON autodiscover with query parameters"""
    # Extract just the email part if there are query parameters
    email_only = email_address.split('?')[0] if '?' in email_address else email_address
    return await autodiscover_json(email_only, request)

# Microsoft Autodiscover Specification Compliance
# Based on: https://learn.microsoft.com/en-us/previous-versions/office/developer/exchange-server-interoperability-guidance/hh352638(v=exchg.140)

# Additional autodiscover endpoints for Microsoft specification compliance
@router.get("/autodiscover/autodiscover.xml")
@router.post("/autodiscover/autodiscover.xml")
async def autodiscover_domain_based(request: Request):
    """Domain-based autodiscover endpoint (step 1 in Microsoft spec)"""
    return await autodiscover(request)

# Error response endpoints for testing Microsoft specification compliance
@router.get("/autodiscover/error/401")
async def autodiscover_error_401():
    """401 Unauthorized response for authentication failures"""
    raise HTTPException(status_code=401, detail="Authentication required")

@router.get("/autodiscover/error/403")
async def autodiscover_error_403():
    """403 Forbidden response for access denied"""
    raise HTTPException(status_code=403, detail="Access denied")

@router.get("/autodiscover/error/404")
async def autodiscover_error_404():
    """404 Not Found response for missing autodiscover"""
    raise HTTPException(status_code=404, detail="Autodiscover service not found")

@router.get("/autodiscover/error/500")
async def autodiscover_error_500():
    """500 Internal Server Error response for server errors"""
    raise HTTPException(status_code=500, detail="Internal server error")

# Redirect response endpoints for testing Microsoft specification compliance
@router.get("/autodiscover/redirect/302")
async def autodiscover_redirect_302(request: Request):
    """302 Redirect response with Location header"""
    host = settings.HOSTNAME or request.headers.get("Host", "")
    redirect_url = f"https://{host}/Autodiscover/Autodiscover.xml"
    
    log_autodiscover("redirect_302", {
        "ip": (request.client.host if request.client else None),
        "ua": request.headers.get("User-Agent"),
        "host": request.headers.get("Host"),
        "redirect_url": redirect_url
    })
    
    return RedirectResponse(url=redirect_url, status_code=302)

@router.get("/autodiscover/redirect/451")
async def autodiscover_redirect_451(request: Request):
    """451 Redirect response with X-MS-Location header"""
    host = settings.HOSTNAME or request.headers.get("Host", "")
    new_url = f"https://{host}/Microsoft-Server-ActiveSync"
    
    log_autodiscover("redirect_451", {
        "ip": (request.client.host if request.client else None),
        "ua": request.headers.get("User-Agent"),
        "host": request.headers.get("Host"),
        "new_url": new_url
    })
    
    response = Response(
        content="",
        status_code=451,
        headers={
            "X-MS-Location": new_url,
            "Cache-Control": "private",
            "Content-Length": "0"
        }
    )
    return response
