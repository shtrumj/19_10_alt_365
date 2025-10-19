from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import Email
from ..dependencies import get_db
from ..schemas import EmailCreate, EmailOut

router = APIRouter(prefix="/emails", tags=["emails"])


@router.post("", response_model=EmailOut, status_code=status.HTTP_201_CREATED)
def create_email(payload: EmailCreate, db: Session = Depends(get_db)):
    email = Email(
        subject=payload.subject,
        body=payload.body,
        body_html=payload.body_html,
        mime_content=payload.mime_content,
        mime_content_type=payload.mime_content_type,
        sender_id=payload.sender_id,
        recipient_id=payload.recipient_id,
        is_external=payload.is_external,
        external_sender=payload.external_sender,
        external_recipient=payload.external_recipient,
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


@router.get("", response_model=List[EmailOut])
def list_emails(
    user_id: Optional[int] = Query(
        None, description="Filter by recipient user id", alias="recipient_id"
    ),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Email)
    if user_id is not None:
        query = query.filter(Email.recipient_id == user_id)
    emails = (
        query.order_by(Email.created_at.desc()).limit(limit).all()
    )
    return emails


@router.get("/{email_id}", response_model=EmailOut)
def get_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email {email_id} not found",
        )
    return email
