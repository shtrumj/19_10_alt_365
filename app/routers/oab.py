"""
Offline Address Book (OAB) Implementation

This module provides OAB functionality for Outlook clients to download
and cache the Global Address List locally.

Key endpoints:
- /oab/oab.xml: OAB manifest file
- /oab/{oab_id}/oab.xml: Specific OAB version
- /oab/{oab_id}/{file}: OAB data files

References:
- [MS-OXWOAB]: Offline Address Book (OAB) File Format and Schema
- [MS-OXOAB]: Offline Address Book (OAB) Protocol
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db, User
from ..diagnostic_logger import log_oab

logger = logging.getLogger(__name__)
router = APIRouter()

# OAB Configuration
OAB_VERSION = "4.0"
OAB_ID = "default-oab"
OAB_DN = "/o=First Organization/ou=Exchange Administrative Group/cn=addrlists/cn=oabs/cn=default offline address book"

@router.get("/oab/oab.xml")
async def oab_manifest(request: Request, db: Session = Depends(get_db)):
    """OAB manifest file - tells Outlook about available address books"""
    
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    log_oab("manifest_request", {
        "client_ip": client_ip,
        "user_agent": user_agent,
        "oab_id": OAB_ID
    })
    
    # Get user count for OAB size estimation
    user_count = db.query(User).count()
    
    # Generate OAB manifest XML
    manifest_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<OAB xmlns="http://schemas.microsoft.com/exchange/2003/oab" 
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://schemas.microsoft.com/exchange/2003/oab oab.xsd">
  <OAL>
    <Name>Default Global Address List</Name>
    <DN>{OAB_DN}</DN>
    <Id>{OAB_ID}</Id>
    <Version>{OAB_VERSION}</Version>
    <Size>{user_count * 1024}</Size>
    <LastModified>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</LastModified>
    <Files>
      <File>
        <Name>browse.oab</Name>
        <Size>{user_count * 512}</Size>
        <SHA1>0000000000000000000000000000000000000000</SHA1>
      </File>
      <File>
        <Name>details.oab</Name>
        <Size>{user_count * 256}</Size>
        <SHA1>1111111111111111111111111111111111111111</SHA1>
      </File>
      <File>
        <Name>rdndex.oab</Name>
        <Size>4096</Size>
        <SHA1>2222222222222222222222222222222222222222</SHA1>
      </File>
    </Files>
  </OAL>
</OAB>"""
    
    log_oab("manifest_response", {
        "oab_id": OAB_ID,
        "user_count": user_count,
        "version": OAB_VERSION
    })
    
    return Response(
        content=manifest_xml,
        media_type="application/xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Type": "application/xml; charset=utf-8"
        }
    )

@router.get("/oab/{oab_id}/oab.xml")
async def oab_version_manifest(oab_id: str, request: Request, db: Session = Depends(get_db)):
    """OAB version-specific manifest"""
    
    if oab_id != OAB_ID:
        raise HTTPException(status_code=404, detail="OAB not found")
    
    # Return the same manifest for now
    return await oab_manifest(request, db)

@router.get("/oab/{oab_id}/browse.oab")
async def oab_browse_file(oab_id: str, request: Request, db: Session = Depends(get_db)):
    """OAB browse file - contains basic user information for browsing"""
    
    if oab_id != OAB_ID:
        raise HTTPException(status_code=404, detail="OAB not found")
    
    log_oab("browse_request", {"oab_id": oab_id})
    
    # Get all users for the address book
    users = db.query(User).order_by(User.full_name.asc()).all()
    
    # Create a simplified OAB browse file
    # In a real implementation, this would be binary OAB format
    # For now, we'll create a minimal structure
    
    oab_data = b"OAB4"  # OAB version 4 header
    oab_data += len(users).to_bytes(4, byteorder='little')  # User count
    
    for user in users:
        # Add user entry (simplified format)
        display_name = (user.full_name or user.username or "").encode('utf-8')[:64]
        email = (user.email or "").encode('utf-8')[:128]
        
        oab_data += len(display_name).to_bytes(2, byteorder='little')
        oab_data += display_name
        oab_data += len(email).to_bytes(2, byteorder='little')
        oab_data += email
    
    log_oab("browse_response", {
        "oab_id": oab_id,
        "user_count": len(users),
        "data_size": len(oab_data)
    })
    
    return Response(
        content=oab_data,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "public, max-age=1800",
            "Content-Type": "application/octet-stream"
        }
    )

@router.get("/oab/{oab_id}/details.oab")
async def oab_details_file(oab_id: str, request: Request, db: Session = Depends(get_db)):
    """OAB details file - contains detailed user properties"""
    
    if oab_id != OAB_ID:
        raise HTTPException(status_code=404, detail="OAB not found")
    
    log_oab("details_request", {"oab_id": oab_id})
    
    # Create minimal details file
    details_data = b"OABD"  # OAB details header
    details_data += b"\x00" * 1024  # Minimal details data
    
    log_oab("details_response", {
        "oab_id": oab_id,
        "data_size": len(details_data)
    })
    
    return Response(
        content=details_data,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "public, max-age=1800",
            "Content-Type": "application/octet-stream"
        }
    )

@router.get("/oab/{oab_id}/rdndex.oab")
async def oab_rdndex_file(oab_id: str, request: Request):
    """OAB RDN index file - contains distinguished name index"""
    
    if oab_id != OAB_ID:
        raise HTTPException(status_code=404, detail="OAB not found")
    
    log_oab("rdndex_request", {"oab_id": oab_id})
    
    # Create minimal RDN index file
    rdndex_data = b"OABR"  # OAB RDN index header
    rdndex_data += b"\x00" * 4092  # Minimal index data
    
    log_oab("rdndex_response", {
        "oab_id": oab_id,
        "data_size": len(rdndex_data)
    })
    
    return Response(
        content=rdndex_data,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Type": "application/octet-stream"
        }
    )
