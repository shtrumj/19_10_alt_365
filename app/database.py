from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from .config import settings
import os

# Prefer environment/config-provided database URL; fallback to local file
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL if hasattr(settings, "DATABASE_URL") else "sqlite:///./email_system.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    admin = Column(Boolean, default=False)  # Admin flag for auditing/management
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sent_emails = relationship("Email", foreign_keys="Email.sender_id", back_populates="sender")
    received_emails = relationship("Email", foreign_keys="Email.recipient_id", back_populates="recipient")

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for external senders
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for external emails
    is_read = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_external = Column(Boolean, default=False)  # Flag for external emails
    external_sender = Column(String, nullable=True)  # Email address for external senders
    external_recipient = Column(String, nullable=True)  # Email address for external recipients
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_emails")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_emails")

class EmailAttachment(Base):
    __tablename__ = "email_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    location = Column(String)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_all_day = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActiveSyncDevice(Base):
    __tablename__ = "activesync_devices"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False)
    device_type = Column(String, nullable=True)
    policy_key = Column(String, nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'device_id', name='uq_user_device'),)

class ActiveSyncState(Base):
    __tablename__ = "activesync_state"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False)
    collection_id = Column(String, nullable=False, default="1")
    sync_key = Column(String, nullable=False, default="1")
    last_sync = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'device_id', 'collection_id', name='uq_user_device_collection'),)

def create_tables():
    Base.metadata.create_all(bind=engine)

def ensure_admin_column():
    """Ensure the users.admin column exists (SQLite-safe)."""
    try:
        # Check pragma table info for users
        with engine.connect() as conn:
            result = conn.execute("PRAGMA table_info(users)").fetchall()
            columns = {row[1] for row in result}
            if 'admin' not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN admin BOOLEAN DEFAULT 0")
    except Exception:
        # Best-effort; ignore if fails (column may already exist or locked)
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
        if user and not getattr(user, 'admin', False):
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
