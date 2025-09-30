"""
Calendar router for Exchange-compatible calendar operations
"""

from datetime import datetime, timedelta
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user_from_cookie
from ..database import User, get_db
from ..models import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarFolderCreate,
    CalendarFolderResponse,
    CalendarFolderTree,
)
from ..services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


# Calendar Folder Endpoints
@router.get("/folders", response_model=List[CalendarFolderTree])
def get_calendar_folders(
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Get calendar folder tree"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    return service.get_calendar_folder_tree(current_user.id)


@router.post("/folders", response_model=CalendarFolderResponse)
def create_calendar_folder(
    folder_data: CalendarFolderCreate,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Create a new calendar folder"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    folder = service.create_calendar_folder(current_user.id, folder_data)
    return CalendarFolderResponse.from_orm(folder)


@router.get("/folders/{folder_id}", response_model=CalendarFolderResponse)
def get_calendar_folder(
    folder_id: int,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Get a specific calendar folder"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    folder = service.get_calendar_folder(folder_id, current_user.id)
    if not folder:
        raise HTTPException(status_code=404, detail="Calendar folder not found")
    return CalendarFolderResponse.from_orm(folder)


@router.put("/folders/{folder_id}", response_model=CalendarFolderResponse)
def update_calendar_folder(
    folder_id: int,
    folder_data: CalendarFolderCreate,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Update a calendar folder"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    folder = service.update_calendar_folder(folder_id, current_user.id, folder_data)
    if not folder:
        raise HTTPException(status_code=404, detail="Calendar folder not found")
    return CalendarFolderResponse.from_orm(folder)


@router.delete("/folders/{folder_id}")
def delete_calendar_folder(
    folder_id: int,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Delete a calendar folder"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    success = service.delete_calendar_folder(folder_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Calendar folder not found or cannot be deleted"
        )
    return {"message": "Calendar folder deleted successfully"}


# Calendar Event Endpoints
@router.get("/events", response_model=List[CalendarEventResponse])
def get_calendar_events(
    folder_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Get calendar events with optional filtering"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    events = service.get_calendar_events(
        current_user.id, folder_id=folder_id, start_date=start_date, end_date=end_date
    )
    return [CalendarEventResponse.from_orm(event) for event in events]


@router.post("/events", response_model=CalendarEventResponse)
def create_calendar_event(
    event_data: CalendarEventCreate,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Create a new calendar event"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    event = service.create_calendar_event(current_user.id, event_data)
    return CalendarEventResponse.from_orm(event)


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_calendar_event(
    event_id: int,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Get a specific calendar event"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    event = service.get_calendar_event(event_id, current_user.id)
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return CalendarEventResponse.from_orm(event)


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
def update_calendar_event(
    event_id: int,
    event_data: CalendarEventCreate,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Update a calendar event"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    event = service.update_calendar_event(event_id, current_user.id, event_data)
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return CalendarEventResponse.from_orm(event)


@router.delete("/events/{event_id}")
def delete_calendar_event(
    event_id: int,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Delete a calendar event"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    success = service.delete_calendar_event(event_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return {"message": "Calendar event deleted successfully"}


@router.get("/events/upcoming", response_model=List[CalendarEventResponse])
def get_upcoming_events(
    days: int = 7,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Get upcoming events for the next N days"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    service = CalendarService(db)
    events = service.get_upcoming_events(current_user.id, days)
    return [CalendarEventResponse.from_orm(event) for event in events]


# OWA Calendar UI Endpoints
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def calendar_home(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Calendar home page"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    from ..routers.owa import get_template_context

    context = get_template_context(request, current_user=current_user)

    # Get calendar data
    service = CalendarService(db)
    folders = service.get_calendar_folder_tree(current_user.id)
    upcoming_events = service.get_upcoming_events(current_user.id, 7)

    context.update(
        {
            "folders": folders,
            "upcoming_events": upcoming_events,
            "active_folder_uuid": folders[0].uuid if folders else None,
        }
    )

    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="templates/owa")
    return templates.TemplateResponse("calendar.html", context)


@router.get("/test")
def calendar_test():
    """Test endpoint for calendar router"""
    return {"message": "Calendar router is working"}
