from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


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
    body_html: Optional[str] = None


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
    mime_content: Optional[str] = None
    mime_content_type: Optional[str] = None

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
            recipient_email=(
                email.recipient.email if email.recipient else email.external_recipient
            ),
            is_read=email.is_read,
            created_at=email.created_at,
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


class ContactFolderBase(BaseModel):
    uuid: str
    display_name: str
    parent_uuid: Optional[str] = None
    well_known_name: Optional[str] = None
    is_default: bool = False
    description: Optional[str] = None


class ContactFolderTree(ContactFolderBase):
    children: List["ContactFolderTree"] = []


class ContactBase(BaseModel):
    uuid: str
    folder_uuid: Optional[str] = None
    display_name: Optional[str] = None
    file_as: Optional[str] = None
    given_name: Optional[str] = None
    middle_name: Optional[str] = None
    surname: Optional[str] = None
    nick_name: Optional[str] = None
    initials: Optional[str] = None
    suffix: Optional[str] = None
    title: Optional[str] = None
    company_name: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    manager: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_phone: Optional[str] = None
    spouse_partner_name: Optional[str] = None
    children: Optional[List[str]] = None
    email_address_1: Optional[str] = None
    email_address_2: Optional[str] = None
    email_address_3: Optional[str] = None
    im_address: Optional[str] = None
    web_page: Optional[str] = None
    business_phone: Optional[str] = None
    business_phone_2: Optional[str] = None
    business_fax: Optional[str] = None
    home_phone: Optional[str] = None
    home_phone_2: Optional[str] = None
    home_fax: Optional[str] = None
    mobile_phone: Optional[str] = None
    pager: Optional[str] = None
    other_phone: Optional[str] = None
    other_fax: Optional[str] = None
    callback: Optional[str] = None
    car_phone: Optional[str] = None
    radio_phone: Optional[str] = None
    tty_tdd_phone: Optional[str] = None
    telex: Optional[str] = None
    business_address_street: Optional[str] = None
    business_address_city: Optional[str] = None
    business_address_state: Optional[str] = None
    business_address_postal_code: Optional[str] = None
    business_address_country: Optional[str] = None
    home_address_street: Optional[str] = None
    home_address_city: Optional[str] = None
    home_address_state: Optional[str] = None
    home_address_postal_code: Optional[str] = None
    home_address_country: Optional[str] = None
    other_address_street: Optional[str] = None
    other_address_city: Optional[str] = None
    other_address_state: Optional[str] = None
    other_address_postal_code: Optional[str] = None
    other_address_country: Optional[str] = None
    birthday: Optional[datetime] = None
    anniversary: Optional[datetime] = None
    notes: Optional[str] = None
    categories: Optional[List[str]] = None
    sensitivity: Optional[str] = None
    gender: Optional[str] = None


class ContactResponse(ContactBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Calendar Folder Models
class CalendarFolderBase(BaseModel):
    display_name: str
    description: Optional[str] = None
    color: Optional[str] = "#0078d4"
    parent_id: Optional[int] = None


class CalendarFolderCreate(CalendarFolderBase):
    pass


class CalendarFolderResponse(CalendarFolderBase):
    id: int
    uuid: str
    owner_id: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarFolderTree(CalendarFolderResponse):
    children: List["CalendarFolderTree"] = []

    class Config:
        from_attributes = True


# Calendar Event Models
class AttendeeBase(BaseModel):
    email: str
    name: Optional[str] = None
    response_status: Optional[str] = "none"  # none, accepted, declined, tentative
    attendee_type: Optional[str] = "required"  # required, optional, resource


class CalendarEventBase(BaseModel):
    subject: str
    body: Optional[str] = None
    body_type: Optional[str] = "text"  # text, html
    importance: Optional[str] = "normal"  # low, normal, high
    sensitivity: Optional[str] = "normal"  # normal, personal, private, confidential
    is_all_day: Optional[bool] = False
    start_time: datetime
    end_time: datetime
    timezone: Optional[str] = "UTC"
    location: Optional[str] = None
    is_meeting: Optional[bool] = False
    is_online_meeting: Optional[bool] = False
    online_meeting_provider: Optional[str] = None
    online_meeting_url: Optional[str] = None
    online_meeting_phone: Optional[str] = None
    attendees: Optional[List[AttendeeBase]] = []
    organizer: Optional[str] = None
    meeting_status: Optional[str] = "free"  # free, tentative, busy, oof
    response_status: Optional[str] = "none"  # none, accepted, declined, tentative
    response_requested: Optional[bool] = False
    reminder_set: Optional[bool] = False
    reminder_minutes: Optional[int] = 15
    categories: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    folder_id: Optional[int] = None


class CalendarEventCreate(CalendarEventBase):
    pass


class CalendarEventResponse(CalendarEventBase):
    id: int
    uuid: str
    owner_id: int
    is_recurring: bool
    recurrence_pattern: Optional[str] = None
    recurrence_start: Optional[datetime] = None
    recurrence_end: Optional[datetime] = None
    recurrence_count: Optional[int] = None
    change_key: str
    item_class: str
    created_at: datetime
    updated_at: datetime
    last_modified: datetime

    class Config:
        from_attributes = True


# Update forward references
CalendarFolderTree.model_rebuild()
