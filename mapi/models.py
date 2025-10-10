"""
MAPI/HTTP Database Models

SQLAlchemy models for MAPI session management and object storage.
"""

from datetime import datetime, timedelta

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MapiSession(Base):
    """
    MAPI/HTTP session.

    Represents an active connection from an Outlook client.
    """

    __tablename__ = "mapi_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Session metadata
    context_handle = Column(LargeBinary)  # Opaque context handle
    client_info = Column(String(255))  # X-ClientInfo header
    user_agent = Column(String(255))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="mapi_sessions")
    objects = relationship(
        "MapiObject", back_populates="session", cascade="all, delete-orphan"
    )
    subscriptions = relationship(
        "MapiSubscription", back_populates="session", cascade="all, delete-orphan"
    )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at

    def refresh(self, timeout_minutes: int = 30):
        """Refresh session expiration."""
        self.last_activity = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)


class MapiObject(Base):
    """
    MAPI object handle.

    Represents an open object (folder, message, attachment, table) within a session.
    """

    __tablename__ = "mapi_objects"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        String(64),
        ForeignKey("mapi_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Object identification
    handle = Column(Integer, nullable=False)  # Client-side handle (0-255)
    object_type = Column(
        String(32), nullable=False
    )  # folder, message, attachment, table

    # Entity reference
    entity_type = Column(String(32))  # email, folder, attachment
    entity_id = Column(Integer)  # References emails.id, etc.

    # Property storage
    properties = Column(JSON)  # Cached properties

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("MapiSession", back_populates="objects")

    def __repr__(self):
        return f"<MapiObject handle={self.handle} type={self.object_type} entity={self.entity_type}:{self.entity_id}>"


class MapiSubscription(Base):
    """
    MAPI notification subscription.

    Represents a client subscription to server events (new mail, folder changes, etc.).
    """

    __tablename__ = "mapi_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        String(64),
        ForeignKey("mapi_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Subscription configuration
    subscription_id = Column(Integer, nullable=False)
    folder_id = Column(Integer)  # Folder to monitor (None = all folders)
    notification_types = Column(Integer, nullable=False)  # Bitmask of event types

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("MapiSession", back_populates="subscriptions")

    def __repr__(self):
        return f"<MapiSubscription id={self.subscription_id} folder={self.folder_id} active={self.is_active}>"


class MapiSyncState(Base):
    """
    MAPI synchronization state.

    Tracks sync state for folder contents (ICS - Incremental Change Synchronization).
    """

    __tablename__ = "mapi_sync_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, nullable=False)

    # Sync state
    sync_state = Column(LargeBinary)  # Opaque sync state blob
    last_sync_time = Column(DateTime)

    # ICS counters
    last_cn = Column(Integer, default=0)  # Last change number
    last_mid = Column(Integer, default=0)  # Last message ID

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<MapiSyncState user={self.user_id} folder={self.folder_id} cn={self.last_cn}>"
