from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from ..database import get_db, User
from ..models import EmailCreate, EmailResponse, EmailSummary
from ..auth import get_current_user, get_current_user_from_cookie
from ..email_service import EmailService
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/emails", tags=["emails"])

@router.post("/send", response_model=EmailResponse)
def send_email(
    email_data: EmailCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a new email"""
    email_service = EmailService(db)
    try:
        email = email_service.send_email(email_data, current_user.id)
        return email
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send email")

@router.get("/", response_model=List[EmailSummary])
def get_emails(
    request: Request,
    folder: str = Query("inbox", description="Email folder: inbox, sent, deleted"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Get emails for the current user"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    email_service = EmailService(db)
    emails = email_service.get_user_emails(current_user.id, folder, limit, offset)
    return [EmailSummary.from_email(email) for email in emails]

@router.get("/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: int,
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Get a specific email by ID"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    email_service = EmailService(db)
    email = email_service.get_email_by_id(email_id, current_user.id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Mark as read if it's an inbox email
    if email.recipient_id == current_user.id and not email.is_read:
        email_service.mark_as_read(email_id, current_user.id)
    
    return email

@router.put("/{email_id}/read")
def mark_email_as_read(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an email as read"""
    email_service = EmailService(db)
    success = email_service.mark_as_read(email_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"message": "Email marked as read"}

@router.delete("/{email_id}")
def delete_email(
    email_id: int,
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Delete an email"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    email_service = EmailService(db)
    success = email_service.delete_email(email_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Email not found")
    return {"message": "Email deleted"}

@router.get("/stats/summary")
def get_email_stats(
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Get email statistics for the current user (cookie-auth for OWA)."""
    if isinstance(current_user, RedirectResponse):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    email_service = EmailService(db)
    inbox_emails = email_service.get_user_emails(current_user.id, "inbox")
    sent_emails = email_service.get_user_emails(current_user.id, "sent")
    unread_count = sum(1 for email in inbox_emails if not email.is_read)
    
    return {
        "inbox_count": len(inbox_emails),
        "sent_count": len(sent_emails),
        "unread_count": unread_count
    }
