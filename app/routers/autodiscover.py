from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, RedirectResponse
from ..config import settings
from ..database import SessionLocal, User
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
    mobilesync_url = f"https://{host}/activesync/Microsoft-Server-ActiveSync"
    
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
    
    xml = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
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
        <ServerVersionInfo MajorVersion="15" MinorVersion="1" MajorBuildNumber="2507" MinorBuildNumber="27" Version="Exchange2016" />
        <AD>owa.shtrum.com</AD>
        <NetworkRequirements>On</NetworkRequirements>
        <AddressBookNetworkRequirements>On</AddressBookNetworkRequirements>
        <EwsUrl>{ews_url}</EwsUrl>
        <EcpUrl>{owa_url}</EcpUrl>
        <EmwsUrl>{ews_url}</EmwsUrl>
        <SharingUrl>{owa_url}/sharing</SharingUrl>
        <EcpUrl-um>{owa_url}/ecp/um</EcpUrl-um>
        <EcpUrl-aggr>{owa_url}/ecp/aggr</EcpUrl-aggr>
        <EcpUrl-mt>{owa_url}/ecp/mt</EcpUrl-mt>
        <EcpUrl-ret>{owa_url}/ecp/ret</EcpUrl-ret>
        <EcpUrl-sms>{owa_url}/ecp/sms</EcpUrl-sms>
        <EcpUrl-publish>{owa_url}/ecp/publish</EcpUrl-publish>
        <EcpUrl-photo>{owa_url}/ecp/photo</EcpUrl-photo>
        <EcpUrl-connect>{owa_url}/ecp/connect</EcpUrl-connect>
        <EcpUrl-tm>{owa_url}/ecp/tm</EcpUrl-tm>
        <EcpUrl-tmCreating>{owa_url}/ecp/tmCreating</EcpUrl-tmCreating>
        <EcpUrl-tmHiding>{owa_url}/ecp/tmHiding</EcpUrl-tmHiding>
        <EcpUrl-tmEditing>{owa_url}/ecp/tmEditing</EcpUrl-tmEditing>
        <EcpUrl-extinstall>{owa_url}/ecp/extinstall</EcpUrl-extinstall>
        <PublicFolderServer>{exch_server}</PublicFolderServer>
        <PublicFolderServerDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Configuration/cn=Servers/cn={exch_server}</PublicFolderServerDN>
        <ActiveDirectoryServer>owa.shtrum.com</ActiveDirectoryServer>
        <ReferralDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)</ReferralDN>
        <ExchangeRpcUrl>https://{host}/rpc/rpcproxy.dll</ExchangeRpcUrl>
        <RpcUrl>https://{host}/rpc/rpcproxy.dll</RpcUrl>
        <EwsPartnerUrl>{ews_url}</EwsPartnerUrl>
        <LoginName>shtrum\\yonatan</LoginName>
        <MSOnline>false</MSOnline>
        <MailboxDNEx>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Recipients/cn={user_part}</MailboxDNEx>
        <Database>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Configuration/cn=Servers/cn={exch_server}/cn=InformationStore/cn=First Storage Group/cn=Mailbox Store ({exch_server})</Database>
        <RoutingType>SMTP</RoutingType>
        <SmtpAddress>yonatan@shtrum.com</SmtpAddress>
        <LegacyDN>/o=First Organization/ou=Exchange Administrative Group (FYDIBOHF23SPDLT)/cn=Recipients/cn={user_part}</LegacyDN>
        <DeploymentId>00000000-0000-0000-0000-000000000000</DeploymentId>
        <NetworkLocation>Inside</NetworkLocation>
        <Internal>
          <Url>{mapi_server_url}</Url>
          <EwsUrl>{ews_url}</EwsUrl>
          <OOFUrl>{owa_url}/oof</OOFUrl>
          <UMUrl>{owa_url}/um</UMUrl>
          <OABUrl>https://{host}/oab/oab.xml</OABUrl>
          <ServerExclusiveConnect>On</ServerExclusiveConnect>
          <ASUrl>https://{host}/activesync/Microsoft-Server-ActiveSync</ASUrl>
          <EwsPartnerUrl>{ews_url}</EwsPartnerUrl>
          <CertPrincipalName>msstd:{exch_server}</CertPrincipalName>
          <GroupingInformation>Exchange</GroupingInformation>
        </Internal>
        <External>
          <Url>{mapi_server_url}</Url>
          <EwsUrl>{ews_url}</EwsUrl>
          <OOFUrl>{owa_url}/oof</OOFUrl>
          <UMUrl>{owa_url}/um</UMUrl>
          <OABUrl>https://{host}/oab/oab.xml</OABUrl>
          <ServerExclusiveConnect>On</ServerExclusiveConnect>
          <ASUrl>https://{host}/activesync/Microsoft-Server-ActiveSync</ASUrl>
          <EwsPartnerUrl>{ews_url}</EwsPartnerUrl>
          <CertPrincipalName>msstd:{exch_server}</CertPrincipalName>
          <GroupingInformation>Exchange</GroupingInformation>
        </External>
        <AlternateMailboxes/>
        <MailboxSmtpAddress>yonatan@shtrum.com</MailboxSmtpAddress>
        <SpamFilteringEnabled>false</SpamFilteringEnabled>
        <PrimarySmtpAddress>yonatan@shtrum.com</PrimarySmtpAddress>
        <CrossOrganizationSharingEnabled>false</CrossOrganizationSharingEnabled>
        <FreeBusyViewType>None</FreeBusyViewType>
        <IsGCenabled>false</IsGCenabled>
        <BisDirSyncEnabled>false</BisDirSyncEnabled>
        <IsOrgPersonEnabled>false</IsOrgPersonEnabled>
        <IsMixedMode>false</IsMixedMode>
        <IsDehydratedEnabled>false</IsDehydratedEnabled>
        <IsTenantToTenantMigrationEnabled>false</IsTenantToTenantMigrationEnabled>
        <SiteMailboxCreationURL>{owa_url}/ecp/siteMailbox</SiteMailboxCreationURL>
        <DomainRequired>false</DomainRequired>
        <DomainController>owa.shtrum.com</DomainController>
        <AuthRequired>true</AuthRequired>
        <AuthPackage>Ntlm</AuthPackage>
        <UsePrincipalName>false</UsePrincipalName>
        <ExchangeVersion>15.01.2507.027</ExchangeVersion>
        <MapiHttpEnabled>true</MapiHttpEnabled>
        <EncryptionRequired>false</EncryptionRequired>
        <MapiHttpVersion>2</MapiHttpVersion>
        <MapiHttpServerUrl>{mapi_server_url}</MapiHttpServerUrl>
        <ExternalHostname>{exch_server}</ExternalHostname>
        <ExternalUrl>{mapi_server_url}</ExternalUrl>
        <InternalHostname>{exch_server}</InternalHostname>
        <InternalUrl>{mapi_server_url}</InternalUrl>
        <TTL>1</TTL>
        <InternalPop3Connections>
          <Hostname>{exch_server}</Hostname>
          <Port>995</Port>
          <EncryptionMethod>SSL</EncryptionMethod>
        </InternalPop3Connections>
        <InternalImap4Connections>
          <Hostname>{exch_server}</Hostname>
          <Port>993</Port>
          <EncryptionMethod>SSL</EncryptionMethod>
        </InternalImap4Connections>
        <InternalSmtpConnections>
          <Hostname>{exch_server}</Hostname>
          <Port>587</Port>
          <EncryptionMethod>TLS</EncryptionMethod>
        </InternalSmtpConnections>
        <ExternalPop3Connections>
          <Hostname>{exch_server}</Hostname>
          <Port>995</Port>
          <EncryptionMethod>SSL</EncryptionMethod>
        </ExternalPop3Connections>
        <ExternalImap4Connections>
          <Hostname>{exch_server}</Hostname>
          <Port>993</Port>
          <EncryptionMethod>SSL</EncryptionMethod>
        </ExternalImap4Connections>
        <ExternalSmtpConnections>
          <Hostname>{exch_server}</Hostname>
          <Port>587</Port>
          <EncryptionMethod>TLS</EncryptionMethod>
        </ExternalSmtpConnections>
      </Protocol>
      <Protocol>
        <Type>EXPR</Type>
        <Server>{exch_server}</Server>
        <Port>443</Port>
        <SSL>On</SSL>
        <AuthPackage>Ntlm</AuthPackage>
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
    """GET handler for autodiscover - returns full response like POST"""
    host = settings.HOSTNAME or request.headers.get("Host", "")
    
    # Log GET hits as well (browsers, some clients probe with GET)
    try:
        log_autodiscover("get", {
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("User-Agent"),
            "host": request.headers.get("Host"),
        })
    except Exception:
        pass
    
    # Use the same full autodiscover response as POST
    # This ensures Outlook gets all the settings it needs
    return await autodiscover(request)

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
        # Include MAPI HTTP settings that Outlook needs to proceed
        mapi_server_url = f"https://{host}/mapi/emsmdb"
        
        # RESEARCH FINDING: Outlook 2021 has known compatibility issues with JSON autodiscover
        # Many users report Outlook getting stuck after receiving JSON responses
        # Solution: Redirect JSON requests to XML autodiscover for better compatibility
        
        log_autodiscover("json_redirect_to_xml", {
            "email": email_address, 
            "reason": "Outlook 2021 JSON compatibility issues - redirecting to XML",
            "ua": request.headers.get("User-Agent", "")
        })
        
        # Redirect to XML autodiscover which has better Outlook 2021 support
        from fastapi.responses import RedirectResponse
        xml_url = f"https://{host}/Autodiscover/Autodiscover.xml"
        return RedirectResponse(url=xml_url, status_code=302)
        
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


