from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# User Models
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

# Email Models
class EmailBase(BaseModel):
    subject: str
    body: Optional[str] = None
    recipient_email: str

class EmailCreate(EmailBase):
    pass

class EmailResponse(EmailBase):
    id: int
    sender_id: int
    recipient_id: int
    is_read: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    sender: UserResponse
    recipient: UserResponse
    
    class Config:
        from_attributes = True

class EmailList(BaseModel):
    id: int
    subject: str
    sender_email: str
    recipient_email: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class EmailSummary(BaseModel):
    id: int
    subject: str
    sender_email: str
    recipient_email: str
    is_read: bool
    created_at: datetime
    
    @classmethod
    def from_email(cls, email):
        return cls(
            id=email.id,
            subject=email.subject,
            sender_email=email.sender.email if email.sender else email.external_sender,
            recipient_email=email.recipient.email if email.recipient else email.external_recipient,
            is_read=email.is_read,
            created_at=email.created_at
        )

# Token Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Email Attachment Models
class AttachmentBase(BaseModel):
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None

class AttachmentResponse(AttachmentBase):
    id: int
    email_id: int
    file_path: str
    created_at: datetime
    
    class Config:
        from_attributes = True
