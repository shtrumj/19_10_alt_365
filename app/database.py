import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from .config import settings

# Prefer environment/config-provided database URL; fallback to local file
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        settings.DATABASE_URL
        if hasattr(settings, "DATABASE_URL")
        else "sqlite:///./email_system.db"
    ),
)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    admin = Column(Boolean, default=False)  # Admin flag for auditing/management
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Modern Authentication Fields
    # TOTP (Time-based One-Time Password)
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False)
    
    # WebAuthn (FIDO2)
    webauthn_credentials = Column(Text, nullable=True)  # JSON array of credentials
    webauthn_enabled = Column(Boolean, default=False)
    webauthn_challenge = Column(String, nullable=True)  # Temporary challenge storage
    
    # API Key Authentication
    api_key_hash = Column(String, nullable=True)
    api_key_created = Column(DateTime, nullable=True)
    
    # OAuth2
    oauth2_provider = Column(String, nullable=True)  # google, microsoft, etc.
    oauth2_id = Column(String, nullable=True)
    oauth2_access_token = Column(Text, nullable=True)
    oauth2_refresh_token = Column(Text, nullable=True)
    oauth2_token_expires = Column(DateTime, nullable=True)
    
    # SAML
    saml_name_id = Column(String, nullable=True)
    saml_session_index = Column(String, nullable=True)
    
    # LDAP
    ldap_dn = Column(String, nullable=True)  # Distinguished Name
    
    # Kerberos
    kerberos_principal = Column(String, nullable=True)
    
    # Client Certificate
    client_cert_serial = Column(String, nullable=True)
    client_cert_issuer = Column(String, nullable=True)
    
    # Last login tracking
    last_login = Column(DateTime, nullable=True)
    last_login_method = Column(String, nullable=True)  # password, totp, webauthn, etc.

    # Relationships
    sent_emails = relationship(
        "Email", foreign_keys="Email.sender_id", back_populates="sender"
    )
    received_emails = relationship(
        "Email", foreign_keys="Email.recipient_id", back_populates="recipient"
    )
    contacts = relationship("Contact", back_populates="owner")
    contact_folders = relationship("ContactFolder", back_populates="owner")
    calendar_events = relationship("CalendarEvent", back_populates="owner")
    calendar_folders = relationship("CalendarFolder", back_populates="owner")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    subject = Column(String, nullable=False)
    body = Column(Text)
    body_html = Column(Text)
    mime_content = Column(Text)
    mime_content_type = Column(String)
    sender_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Nullable for external senders
    recipient_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Nullable for external emails
    is_read = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_external = Column(Boolean, default=False)  # Flag for external emails
    external_sender = Column(
        String, nullable=True
    )  # Email address for external senders
    external_recipient = Column(
        String, nullable=True
    )  # Email address for external recipients
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sender = relationship(
        "User", foreign_keys=[sender_id], back_populates="sent_emails"
    )
    recipient = relationship(
        "User", foreign_keys=[recipient_id], back_populates="received_emails"
    )

    @property
    def sender_email(self) -> Optional[str]:
        if self.sender:
            return self.sender.email
        return self.external_sender

    @property
    def recipient_email(self) -> Optional[str]:
        if self.recipient:
            return self.recipient.email
        return self.external_recipient


class EmailAttachment(Base):
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class CalendarEvent(Base):
    """Exchange-compatible calendar event"""

    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("calendar_folders.id"), nullable=True)

    # Basic event information
    subject = Column(String, nullable=False, index=True)
    body = Column(Text)
    body_type = Column(String, default="text")  # text, html
    importance = Column(String, default="normal")  # low, normal, high
    sensitivity = Column(
        String, default="normal"
    )  # normal, personal, private, confidential
    is_all_day = Column(Boolean, default=False)

    # Date and time
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    duration = Column(String)  # ISO 8601 duration format
    timezone = Column(String, default="UTC")

    # Recurrence
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(Text)  # JSON string for recurrence rules
    recurrence_start = Column(DateTime)
    recurrence_end = Column(DateTime)
    recurrence_count = Column(Integer)

    # Location and meeting
    location = Column(String)
    is_meeting = Column(Boolean, default=False)
    is_online_meeting = Column(Boolean, default=False)
    online_meeting_provider = Column(String)  # teams, zoom, etc.
    online_meeting_url = Column(String)
    online_meeting_phone = Column(String)

    # Attendees (stored as JSON)
    attendees = Column(Text)  # JSON array of attendee objects
    organizer = Column(String)  # Email of organizer
    required_attendees = Column(Text)  # JSON array
    optional_attendees = Column(Text)  # JSON array
    resources = Column(Text)  # JSON array of resources

    # Status and response
    meeting_status = Column(String, default="free")  # free, tentative, busy, oof
    response_status = Column(
        String, default="none"
    )  # none, accepted, declined, tentative
    response_requested = Column(Boolean, default=False)

    # Reminders
    reminder_set = Column(Boolean, default=False)
    reminder_minutes = Column(Integer, default=15)

    # Categories and tags
    categories = Column(Text)  # JSON array of categories
    tags = Column(Text)  # JSON array of tags

    # Exchange-specific fields
    change_key = Column(String, unique=True, default=lambda: str(uuid4()))
    item_class = Column(String, default="IPM.Appointment")
    mime_content = Column(Text)  # MIME content for Exchange compatibility

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_modified = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="calendar_events")
    folder = relationship("CalendarFolder", back_populates="events")


class ActiveSyncDevice(Base):
    __tablename__ = "activesync_devices"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False)
    device_type = Column(String, nullable=True)
    policy_key = Column(String, nullable=True)
    is_provisioned = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)


class ActiveSyncState(Base):
    __tablename__ = "activesync_state"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False)
    collection_id = Column(String, nullable=False, default="1")
    # Grommunio-style synckey components
    synckey_uuid = Column(String(36), nullable=True)  # UUID for this sync relationship
    synckey_counter = Column(Integer, default=0)  # Counter for sync progression
    # Legacy sync_key kept for backward compatibility
    sync_key = Column(String, nullable=False, default="0")
    # CRITICAL FIX #24: Track pagination for proper email sync
    last_synced_email_id = Column(Integer, default=0)  # Last email ID sent to client
    # Track all server IDs already acknowledged by the client to drive pagination
    synced_email_ids = Column(Text, nullable=True)  # JSON array of previously synced email IDs
    # CRITICAL FIX #26: Two-phase commit - stage pending batches
    pending_sync_key = Column(String, nullable=True)  # SyncKey of pending batch
    pending_max_email_id = Column(Integer, nullable=True)  # Max email ID in pending batch
    pending_item_ids = Column(String, nullable=True)  # JSON array of email IDs in pending batch
    foldersync_attempts = Column(Integer, default=0)
    last_sync = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @property
    def grommunio_synckey(self) -> str:
        """Generate Grommunio-style {UUID}Counter synckey"""
        if not self.synckey_uuid or self.synckey_counter == 0:
            return "0"
        return f"{{{self.synckey_uuid}}}{self.synckey_counter}"
    
    def set_grommunio_synckey(self, synckey: str):
        """Parse and set Grommunio-style synckey"""
        if synckey == "0":
            self.synckey_uuid = None
            self.synckey_counter = 0
            self.sync_key = "0"
        else:
            import re
            match = re.match(r'^\{([0-9A-Za-z-]+)\}([0-9]+)$', synckey)
            if match:
                self.synckey_uuid = match.group(1)
                self.synckey_counter = int(match.group(2))
                self.sync_key = str(self.synckey_counter)  # Legacy field
            else:
                raise ValueError(f"Invalid synckey format: {synckey}")
    __table_args__ = (
        UniqueConstraint(
            "user_id", "device_id", "collection_id", name="uq_user_device_collection"
        ),
    )


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("contact_folders.id"), nullable=True)
    display_name = Column(String, index=True)
    file_as = Column(String)
    given_name = Column(String)
    middle_name = Column(String)
    surname = Column(String)
    nick_name = Column(String)
    initials = Column(String)
    suffix = Column(String)
    title = Column(String)
    company_name = Column(String)
    department = Column(String)
    job_title = Column(String)
    office_location = Column(String)
    manager = Column(String)
    assistant_name = Column(String)
    assistant_phone = Column(String)
    spouse_partner_name = Column(String)
    children = Column(Text)
    email_address_1 = Column(String, index=True)
    email_address_2 = Column(String)
    email_address_3 = Column(String)
    im_address = Column(String)
    web_page = Column(String)
    business_phone = Column(String)
    business_phone_2 = Column(String)
    business_fax = Column(String)
    home_phone = Column(String)
    home_phone_2 = Column(String)
    home_fax = Column(String)
    mobile_phone = Column(String)
    pager = Column(String)
    other_phone = Column(String)
    other_fax = Column(String)
    callback = Column(String)
    car_phone = Column(String)
    radio_phone = Column(String)
    tty_tdd_phone = Column(String)
    telex = Column(String)
    business_address_street = Column(String)
    business_address_city = Column(String)
    business_address_state = Column(String)
    business_address_postal_code = Column(String)
    business_address_country = Column(String)
    home_address_street = Column(String)
    home_address_city = Column(String)
    home_address_state = Column(String)
    home_address_postal_code = Column(String)
    home_address_country = Column(String)
    other_address_street = Column(String)
    other_address_city = Column(String)
    other_address_state = Column(String)
    other_address_postal_code = Column(String)
    other_address_country = Column(String)
    birthday = Column(DateTime, nullable=True)
    anniversary = Column(DateTime, nullable=True)
    notes = Column(Text)
    categories = Column(Text)
    sensitivity = Column(String)
    gender = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="contacts")
    folder = relationship("ContactFolder", back_populates="contacts")

    @property
    def folder_uuid(self) -> Optional[str]:
        return self.folder.uuid if self.folder else None


class ContactFolder(Base):
    __tablename__ = "contact_folders"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("contact_folders.id"), nullable=True)
    display_name = Column(String, nullable=False)
    well_known_name = Column(String, nullable=True, index=True)
    is_default = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="contact_folders")
    parent = relationship("ContactFolder", remote_side=[id], back_populates="children")
    children = relationship(
        "ContactFolder",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    contacts = relationship("Contact", back_populates="folder")


class CalendarFolder(Base):
    """Exchange-compatible calendar folder"""

    __tablename__ = "calendar_folders"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid4()))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("calendar_folders.id"), nullable=True)
    display_name = Column(String, nullable=False)
    well_known_name = Column(String, nullable=True, index=True)
    is_default = Column(Boolean, default=False)
    color = Column(String, default="#0078d4")  # Exchange default blue
    description = Column(Text)
    permissions = Column(Text)  # JSON string for folder permissions
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="calendar_folders")
    parent = relationship("CalendarFolder", remote_side=[id], back_populates="children")
    children = relationship(
        "CalendarFolder",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    events = relationship("CalendarEvent", back_populates="folder")


def create_tables():
    Base.metadata.create_all(bind=engine)
    ensure_email_mime_columns()


def _ensure_uuid_for_table(conn, table_name: str):
    try:
        result = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        columns = {row[1] for row in result}
        if "uuid" not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN uuid TEXT")
    except Exception:
        pass


def ensure_uuid_columns_and_backfill():
    """Ensure uuid column exists for key tables and backfill missing values using raw SQL."""
    try:
        with engine.connect() as conn:
            # Drop and recreate calendar tables to ensure correct schema
            try:
                conn.execute(text("DROP TABLE IF EXISTS calendar_events"))
                conn.execute(text("DROP TABLE IF EXISTS calendar_folders"))
                conn.commit()
                print("✅ Dropped existing calendar tables")
            except Exception as e:
                print(f"⚠️ Error dropping calendar tables: {e}")

            # Ensure contact folders table exists
            ContactFolder.__table__.create(bind=engine, checkfirst=True)

            # Ensure calendar tables exist - force creation
            try:
                CalendarFolder.__table__.create(bind=engine, checkfirst=True)
                print("✅ CalendarFolder table created/verified")
            except Exception as e:
                print(f"❌ Error creating CalendarFolder table: {e}")

            try:
                CalendarEvent.__table__.create(bind=engine, checkfirst=True)
                print("✅ CalendarEvent table created/verified")
            except Exception as e:
                print(f"❌ Error creating CalendarEvent table: {e}")

            # Ensure extended contact columns exist
            extended_columns = {
                "folder_id": "INTEGER",
                "file_as": "TEXT",
                "nick_name": "TEXT",
                "initials": "TEXT",
                "suffix": "TEXT",
                "title": "TEXT",
                "department": "TEXT",
                "office_location": "TEXT",
                "manager": "TEXT",
                "assistant_name": "TEXT",
                "assistant_phone": "TEXT",
                "spouse_partner_name": "TEXT",
                "children": "TEXT",
                "email_address_1": "TEXT",
                "email_address_2": "TEXT",
                "email_address_3": "TEXT",
                "im_address": "TEXT",
                "web_page": "TEXT",
                "business_phone_2": "TEXT",
                "business_fax": "TEXT",
                "home_phone": "TEXT",
                "home_phone_2": "TEXT",
                "home_fax": "TEXT",
                "pager": "TEXT",
                "other_phone": "TEXT",
                "other_fax": "TEXT",
                "callback": "TEXT",
                "car_phone": "TEXT",
                "radio_phone": "TEXT",
                "tty_tdd_phone": "TEXT",
                "telex": "TEXT",
                "business_address_street": "TEXT",
                "business_address_city": "TEXT",
                "business_address_state": "TEXT",
                "business_address_postal_code": "TEXT",
                "business_address_country": "TEXT",
                "home_address_street": "TEXT",
                "home_address_city": "TEXT",
                "home_address_state": "TEXT",
                "home_address_postal_code": "TEXT",
                "home_address_country": "TEXT",
                "other_address_street": "TEXT",
                "other_address_city": "TEXT",
                "other_address_state": "TEXT",
                "other_address_postal_code": "TEXT",
                "other_address_country": "TEXT",
                "anniversary": "DATETIME",
                "categories": "TEXT",
                "sensitivity": "TEXT",
                "gender": "TEXT",
            }
            result = conn.execute(text("PRAGMA table_info(contacts)")).fetchall()
            existing_cols = {row[1] for row in result}
            for col_name, col_type in extended_columns.items():
                if col_name not in existing_cols:
                    conn.execute(
                        text(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_type}")
                    )
            conn.commit()

            # Ensure helpful indexes
            folder_indexes = conn.execute(
                text("PRAGMA index_list(contact_folders)")
            ).fetchall()
            folder_index_names = {row[1] for row in folder_indexes}
            if "idx_contact_folders_owner" not in folder_index_names:
                conn.execute(
                    text(
                        "CREATE INDEX idx_contact_folders_owner ON contact_folders(owner_id)"
                    )
                )
                conn.commit()
            if "idx_contact_folders_parent" not in folder_index_names:
                conn.execute(
                    text(
                        "CREATE INDEX idx_contact_folders_parent ON contact_folders(parent_id)"
                    )
                )
                conn.commit()

            contact_indexes = conn.execute(
                text("PRAGMA index_list(contacts)")
            ).fetchall()
            contact_index_names = {row[1] for row in contact_indexes}
            if "idx_contacts_folder_id" not in contact_index_names:
                conn.execute(
                    text("CREATE INDEX idx_contacts_folder_id ON contacts(folder_id)")
                )
                conn.commit()
            if "idx_contacts_email1" not in contact_index_names:
                conn.execute(
                    text(
                        "CREATE INDEX idx_contacts_email1 ON contacts(email_address_1)"
                    )
                )
                conn.commit()
            for tbl in [
                "users",
                "emails",
                "email_attachments",
                "calendar_events",
                "activesync_devices",
                "activesync_state",
                "contacts",
                "contact_folders",
            ]:
                # Check if column exists
                result = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
                columns = {row[1] for row in result}
                if "uuid" not in columns:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN uuid TEXT")
                    conn.commit()

                # Add unique index if not exists
                indexes = conn.execute(f"PRAGMA index_list({tbl})").fetchall()
                index_names = {row[1] for row in indexes}
                if f"idx_{tbl}_uuid" not in index_names:
                    conn.execute(f"CREATE UNIQUE INDEX idx_{tbl}_uuid ON {tbl}(uuid)")
                    conn.commit()

                # Backfill missing UUIDs
                rows = conn.execute(
                    f"SELECT id FROM {tbl} WHERE uuid IS NULL OR uuid = ''"
                ).fetchall()

                for row in rows:
                    row_id = row[0]
                    new_uuid = str(uuid4())
                    conn.execute(
                        f"UPDATE {tbl} SET uuid = '{new_uuid}' WHERE id = {row_id}"
                    )

                conn.commit()
    except Exception as e:
        print(f"Error during UUID migration: {e}")


def ensure_admin_column():
    """Ensure the users.admin column exists (SQLite-safe)."""
    try:
        # Check pragma table info for users
        with engine.connect() as conn:
            result = conn.execute("PRAGMA table_info(users)").fetchall()
            columns = {row[1] for row in result}
            if "admin" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN admin BOOLEAN DEFAULT 0")
    except Exception:
        # Best-effort; ignore if fails (column may already exist or locked)
        pass


def ensure_email_mime_columns():
    """Ensure extended body/mime columns exist on the emails table."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("PRAGMA table_info(emails)")).fetchall()
            columns = {row[1] for row in rows}
            if "body_html" not in columns:
                conn.execute(text("ALTER TABLE emails ADD COLUMN body_html TEXT"))
            if "mime_content" not in columns:
                conn.execute(text("ALTER TABLE emails ADD COLUMN mime_content TEXT"))
            if "mime_content_type" not in columns:
                conn.execute(text("ALTER TABLE emails ADD COLUMN mime_content_type TEXT"))
            conn.commit()
    except Exception:
        pass


def set_admin_user(email: str, username: str | None = None):
    """Set a given user as admin by email or username if provided."""
    db = SessionLocal()
    try:
        user = None
        if email:
            user = db.query(User).filter(User.email == email).first()
        if not user and username:
            user = db.query(User).filter(User.username == username).first()
        if user and not getattr(user, "admin", False):
            user.admin = True
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
