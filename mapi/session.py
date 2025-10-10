"""
MAPI Session Management

Handles MAPI/HTTP session lifecycle and object handles.
"""

import logging
import uuid as uuid_module
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session as DBSession

from app.database import MapiObject, MapiSession, User

from .properties import PropertyStore

logger = logging.getLogger(__name__)


class MapiSessionManager:
    """
    Manages MAPI/HTTP sessions.

    Handles session creation, validation, and cleanup.
    """

    @staticmethod
    def create_session(
        db: DBSession,
        user: User,
        client_info: str = None,
        user_agent: str = None,
        timeout_minutes: int = 30,
    ) -> MapiSession:
        """Create a new MAPI session."""

        session_id = str(uuid_module.uuid4())

        session = MapiSession(
            session_id=session_id,
            user_id=user.id,
            client_info=client_info,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=timeout_minutes),
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"Created MAPI session {session_id} for user {user.email}")

        return session

    @staticmethod
    def get_session(db: DBSession, session_id: str) -> Optional[MapiSession]:
        """Get session by ID."""
        session = (
            db.query(MapiSession).filter(MapiSession.session_id == session_id).first()
        )

        if not session:
            return None

        # Check if expired
        if session.is_expired():
            logger.info(f"MAPI session {session_id} expired")
            db.delete(session)
            db.commit()
            return None

        # Refresh expiration
        session.refresh()
        db.commit()

        return session

    @staticmethod
    def delete_session(db: DBSession, session_id: str):
        """Delete session."""
        session = (
            db.query(MapiSession).filter(MapiSession.session_id == session_id).first()
        )

        if session:
            logger.info(f"Deleted MAPI session {session_id}")
            db.delete(session)
            db.commit()

    @staticmethod
    def cleanup_expired_sessions(db: DBSession):
        """Clean up all expired sessions."""
        now = datetime.utcnow()
        expired = db.query(MapiSession).filter(MapiSession.expires_at < now).all()

        for session in expired:
            logger.info(f"Cleaning up expired session {session.session_id}")
            db.delete(session)

        db.commit()

        return len(expired)


class MapiObjectManager:
    """
    Manages MAPI object handles within a session.

    Each session maintains a table of object handles (0-255) that reference
    folders, messages, attachments, or tables.
    """

    def __init__(self, db: DBSession, session: MapiSession):
        self.db = db
        self.session = session
        self._handle_counter = 0
        self._handle_map: Dict[int, MapiObject] = {}
        self._load_handles()

    def _load_handles(self):
        """Load existing handles from database."""
        objects = (
            self.db.query(MapiObject)
            .filter(MapiObject.session_id == self.session.session_id)
            .all()
        )

        for obj in objects:
            self._handle_map[obj.handle] = obj
            if obj.handle >= self._handle_counter:
                self._handle_counter = obj.handle + 1

    def allocate_handle(
        self,
        object_type: str,
        entity_type: str = None,
        entity_id: int = None,
        properties: PropertyStore = None,
    ) -> MapiObject:
        """
        Allocate a new object handle.

        Args:
            object_type: Type of object (folder, message, attachment, table)
            entity_type: Type of entity (email, folder, attachment)
            entity_id: Database ID of entity
            properties: Initial properties

        Returns:
            MapiObject with allocated handle
        """

        # Find next available handle (0-255)
        handle = self._handle_counter % 256
        while handle in self._handle_map:
            self._handle_counter += 1
            handle = self._handle_counter % 256

        # Create object
        obj = MapiObject(
            session_id=self.session.session_id,
            handle=handle,
            object_type=object_type,
            entity_type=entity_type,
            entity_id=entity_id,
            properties=properties.to_json() if properties else None,
        )

        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

        self._handle_map[handle] = obj
        self._handle_counter += 1

        logger.debug(
            f"Allocated handle {handle} for {object_type} ({entity_type}:{entity_id})"
        )

        return obj

    def get_object(self, handle: int) -> Optional[MapiObject]:
        """Get object by handle."""
        return self._handle_map.get(handle)

    def release_handle(self, handle: int):
        """Release an object handle."""
        if handle in self._handle_map:
            obj = self._handle_map[handle]
            logger.debug(f"Released handle {handle} ({obj.object_type})")

            del self._handle_map[handle]
            self.db.delete(obj)
            self.db.commit()

    def get_properties(self, handle: int) -> Optional[PropertyStore]:
        """Get properties for object."""
        obj = self.get_object(handle)
        if not obj or not obj.properties:
            return None

        return PropertyStore.from_json(obj.properties)

    def set_properties(self, handle: int, properties: PropertyStore):
        """Set properties for object."""
        obj = self.get_object(handle)
        if obj:
            obj.properties = properties.to_json()
            self.db.commit()

    def release_all(self):
        """Release all handles in session."""
        for handle in list(self._handle_map.keys()):
            self.release_handle(handle)


class MapiContext:
    """
    MAPI execution context for a single request/response cycle.

    Maintains session state, object handles, and user context.
    """

    def __init__(self, db: DBSession, session: MapiSession, user: User):
        self.db = db
        self.session = session
        self.user = user
        self.object_manager = MapiObjectManager(db, session)
        self.errors: list = []

    def log_error(self, error_code: int, message: str):
        """Log an error during ROP execution."""
        self.errors.append(
            {
                "error_code": error_code,
                "message": message,
                "timestamp": datetime.utcnow(),
            }
        )
        logger.error(f"MAPI error 0x{error_code:08X}: {message}")

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def get_user_inbox_id(self) -> int:
        """Get user's inbox folder ID."""
        # TODO: Implement proper folder lookup
        # For now, return a fixed ID (1)
        return 1

    def get_user_folders(self) -> list:
        """Get user's folders."""
        # TODO: Implement proper folder enumeration
        # For now, return basic folder structure
        return [
            {"id": 1, "name": "Inbox", "type": "IPF.Note"},
            {"id": 2, "name": "Drafts", "type": "IPF.Note"},
            {"id": 3, "name": "Sent Items", "type": "IPF.Note"},
            {"id": 4, "name": "Deleted Items", "type": "IPF.Note"},
        ]

    def get_folder_messages(self, folder_id: int) -> list:
        """Get messages in a folder."""
        # TODO: Implement proper message enumeration
        from app.database import Email

        # Get user's emails
        emails = (
            self.db.query(Email)
            .filter(Email.recipient_id == self.user.id, Email.is_deleted == False)
            .order_by(Email.created_at.desc())
            .limit(100)
            .all()
        )

        return emails
