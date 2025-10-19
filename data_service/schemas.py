from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class EmailCreate(BaseModel):
    subject: str
    body: Optional[str] = None
    body_html: Optional[str] = None
    mime_content: Optional[str] = None
    mime_content_type: Optional[str] = None
    sender_id: Optional[int] = None
    recipient_id: Optional[int] = None
    is_external: bool = False
    external_sender: Optional[str] = None
    external_recipient: Optional[str] = None


class EmailOut(BaseModel):
    id: int
    uuid: str
    subject: str
    body: Optional[str] = None
    body_html: Optional[str] = None
    sender_id: Optional[int] = None
    recipient_id: Optional[int] = None
    is_external: bool
    external_sender: Optional[str] = None
    external_recipient: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
