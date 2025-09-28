from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from xml.etree import ElementTree as ET
from datetime import datetime
from ..database import get_db, User
from ..auth import get_current_user
from ..email_service import EmailService
from typing import List, Optional

router = APIRouter(prefix="/activesync", tags=["activesync"])

class ActiveSyncResponse:
    def __init__(self, xml_content: str):
        self.xml_content = xml_content
    
    def __call__(self, *args, **kwargs):
        return Response(
            content=self.xml_content,
            media_type="application/vnd.ms-sync.wbxml"
        )

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
        from_elem.text = email.sender.email
        
        # To
        to_elem = ET.SubElement(application_data, "To")
        to_elem.text = email.recipient.email
        
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
    
    return ET.tostring(root, encoding='unicode')

@router.post("/sync")
async def sync_emails(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Device provisioning for ActiveSync"""
    # In a real implementation, this would handle device registration
    return {
        "status": "provisioned",
        "device_id": "device_123",
        "user": current_user.username
    }

@router.get("/folders")
def get_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available email folders for ActiveSync"""
    folders = [
        {"id": "1", "name": "Inbox", "type": "inbox"},
        {"id": "2", "name": "Sent Items", "type": "sent"},
        {"id": "3", "name": "Deleted Items", "type": "deleted"}
    ]
    return {"folders": folders}

@router.get("/folders/{folder_id}/emails")
def get_folder_emails(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get emails from a specific folder for ActiveSync"""
    email_service = EmailService(db)
    
    folder_map = {
        "1": "inbox",
        "2": "sent", 
        "3": "deleted"
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
                "from": email.sender.email,
                "to": email.recipient.email,
                "date": email.created_at.isoformat(),
                "read": email.is_read,
                "body": email.body
            }
            for email in emails
        ]
    }
