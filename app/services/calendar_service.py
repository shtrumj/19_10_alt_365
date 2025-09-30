"""
Calendar service for Exchange-compatible calendar operations
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..database import CalendarEvent, CalendarFolder, User
from ..models import (
    AttendeeBase,
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarFolderCreate,
    CalendarFolderResponse,
    CalendarFolderTree,
)


class CalendarService:
    """Service for managing calendar folders and events"""

    def __init__(self, db: Session):
        self.db = db

    # Calendar Folder Operations
    def create_default_calendar_folder(self, user_id: int) -> CalendarFolder:
        """Create default calendar folder for a user"""
        default_folder = CalendarFolder(
            owner_id=user_id,
            display_name="Calendar",
            well_known_name="calendar",
            is_default=True,
            description="Default calendar folder",
        )
        self.db.add(default_folder)
        self.db.commit()
        self.db.refresh(default_folder)
        return default_folder

    def get_calendar_folders(self, user_id: int) -> List[CalendarFolder]:
        """Get all calendar folders for a user"""
        return (
            self.db.query(CalendarFolder)
            .filter(CalendarFolder.owner_id == user_id)
            .all()
        )

    def get_calendar_folder_tree(self, user_id: int) -> List[CalendarFolderTree]:
        """Get calendar folder tree structure"""
        folders = self.get_calendar_folders(user_id)
        return self._build_folder_tree(folders)

    def _build_folder_tree(
        self, folders: List[CalendarFolder], parent_id: Optional[int] = None
    ) -> List[CalendarFolderTree]:
        """Build hierarchical folder tree"""
        tree = []
        for folder in folders:
            if folder.parent_id == parent_id:
                children = self._build_folder_tree(folders, folder.id)
                folder_tree = CalendarFolderTree(
                    id=folder.id,
                    uuid=folder.uuid,
                    owner_id=folder.owner_id,
                    display_name=folder.display_name,
                    description=folder.description,
                    color=folder.color,
                    parent_id=folder.parent_id,
                    is_default=folder.is_default,
                    created_at=folder.created_at,
                    updated_at=folder.updated_at,
                    children=children,
                )
                tree.append(folder_tree)
        return tree

    def create_calendar_folder(
        self, user_id: int, folder_data: CalendarFolderCreate
    ) -> CalendarFolder:
        """Create a new calendar folder"""
        folder = CalendarFolder(
            owner_id=user_id,
            display_name=folder_data.display_name,
            description=folder_data.description,
            color=folder_data.color,
            parent_id=folder_data.parent_id,
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def get_calendar_folder(
        self, folder_id: int, user_id: int
    ) -> Optional[CalendarFolder]:
        """Get a specific calendar folder"""
        return (
            self.db.query(CalendarFolder)
            .filter(
                and_(CalendarFolder.id == folder_id, CalendarFolder.owner_id == user_id)
            )
            .first()
        )

    def update_calendar_folder(
        self, folder_id: int, user_id: int, folder_data: CalendarFolderCreate
    ) -> Optional[CalendarFolder]:
        """Update a calendar folder"""
        folder = self.get_calendar_folder(folder_id, user_id)
        if folder:
            folder.display_name = folder_data.display_name
            folder.description = folder_data.description
            folder.color = folder_data.color
            folder.parent_id = folder_data.parent_id
            folder.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(folder)
        return folder

    def delete_calendar_folder(self, folder_id: int, user_id: int) -> bool:
        """Delete a calendar folder"""
        folder = self.get_calendar_folder(folder_id, user_id)
        if folder and not folder.is_default:
            self.db.delete(folder)
            self.db.commit()
            return True
        return False

    # Calendar Event Operations
    def create_calendar_event(
        self, user_id: int, event_data: CalendarEventCreate
    ) -> CalendarEvent:
        """Create a new calendar event"""
        # Convert attendees to JSON
        attendees_json = None
        if event_data.attendees:
            attendees_json = json.dumps(
                [attendee.dict() for attendee in event_data.attendees]
            )

        # Calculate duration
        duration = event_data.end_time - event_data.start_time

        event = CalendarEvent(
            owner_id=user_id,
            folder_id=event_data.folder_id,
            subject=event_data.subject,
            body=event_data.body,
            body_type=event_data.body_type,
            importance=event_data.importance,
            sensitivity=event_data.sensitivity,
            is_all_day=event_data.is_all_day,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            duration=str(duration),
            timezone=event_data.timezone,
            location=event_data.location,
            is_meeting=event_data.is_meeting,
            is_online_meeting=event_data.is_online_meeting,
            online_meeting_provider=event_data.online_meeting_provider,
            online_meeting_url=event_data.online_meeting_url,
            online_meeting_phone=event_data.online_meeting_phone,
            attendees=attendees_json,
            organizer=event_data.organizer,
            meeting_status=event_data.meeting_status,
            response_status=event_data.response_status,
            response_requested=event_data.response_requested,
            reminder_set=event_data.reminder_set,
            reminder_minutes=event_data.reminder_minutes,
            categories=(
                json.dumps(event_data.categories) if event_data.categories else None
            ),
            tags=json.dumps(event_data.tags) if event_data.tags else None,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_calendar_events(
        self,
        user_id: int,
        folder_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CalendarEvent]:
        """Get calendar events for a user with optional filtering"""
        query = self.db.query(CalendarEvent).filter(CalendarEvent.owner_id == user_id)

        if folder_id:
            query = query.filter(CalendarEvent.folder_id == folder_id)

        if start_date:
            query = query.filter(CalendarEvent.start_time >= start_date)

        if end_date:
            query = query.filter(CalendarEvent.end_time <= end_date)

        return query.order_by(CalendarEvent.start_time).all()

    def get_calendar_event(
        self, event_id: int, user_id: int
    ) -> Optional[CalendarEvent]:
        """Get a specific calendar event"""
        return (
            self.db.query(CalendarEvent)
            .filter(
                and_(CalendarEvent.id == event_id, CalendarEvent.owner_id == user_id)
            )
            .first()
        )

    def update_calendar_event(
        self, event_id: int, user_id: int, event_data: CalendarEventCreate
    ) -> Optional[CalendarEvent]:
        """Update a calendar event"""
        event = self.get_calendar_event(event_id, user_id)
        if event:
            # Update basic fields
            event.subject = event_data.subject
            event.body = event_data.body
            event.body_type = event_data.body_type
            event.importance = event_data.importance
            event.sensitivity = event_data.sensitivity
            event.is_all_day = event_data.is_all_day
            event.start_time = event_data.start_time
            event.end_time = event_data.end_time
            event.timezone = event_data.timezone
            event.location = event_data.location
            event.is_meeting = event_data.is_meeting
            event.is_online_meeting = event_data.is_online_meeting
            event.online_meeting_provider = event_data.online_meeting_provider
            event.online_meeting_url = event_data.online_meeting_url
            event.online_meeting_phone = event_data.online_meeting_phone
            event.organizer = event_data.organizer
            event.meeting_status = event_data.meeting_status
            event.response_status = event_data.response_status
            event.response_requested = event_data.response_requested
            event.reminder_set = event_data.reminder_set
            event.reminder_minutes = event_data.reminder_minutes
            event.folder_id = event_data.folder_id

            # Update JSON fields
            if event_data.attendees:
                event.attendees = json.dumps(
                    [attendee.dict() for attendee in event_data.attendees]
                )

            if event_data.categories:
                event.categories = json.dumps(event_data.categories)

            if event_data.tags:
                event.tags = json.dumps(event_data.tags)

            # Recalculate duration
            event.duration = str(event_data.end_time - event_data.start_time)
            event.updated_at = datetime.utcnow()
            event.last_modified = datetime.utcnow()

            self.db.commit()
            self.db.refresh(event)
        return event

    def delete_calendar_event(self, event_id: int, user_id: int) -> bool:
        """Delete a calendar event"""
        event = self.get_calendar_event(event_id, user_id)
        if event:
            self.db.delete(event)
            self.db.commit()
            return True
        return False

    def get_events_by_date_range(
        self, user_id: int, start_date: datetime, end_date: datetime
    ) -> List[CalendarEvent]:
        """Get events within a date range"""
        return (
            self.db.query(CalendarEvent)
            .filter(
                and_(
                    CalendarEvent.owner_id == user_id,
                    CalendarEvent.start_time >= start_date,
                    CalendarEvent.end_time <= end_date,
                )
            )
            .order_by(CalendarEvent.start_time)
            .all()
        )

    def get_upcoming_events(self, user_id: int, days: int = 7) -> List[CalendarEvent]:
        """Get upcoming events for the next N days"""
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days)
        return self.get_events_by_date_range(user_id, start_date, end_date)
