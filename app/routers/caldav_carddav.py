from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ..database import get_db, CalendarEvent, Contact

router = APIRouter(prefix="", tags=["caldav-carddav"])  # mounted directly


def _iso(dt: datetime | None) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ") if dt else ""


def _event_to_ical(ev: CalendarEvent) -> str:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//365-Email-System//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:CAL_{ev.id}@local\r\n"
        f"DTSTAMP:{_iso(ev.created_at)}\r\n"
        f"DTSTART:{_iso(ev.start_time)}\r\n"
        f"DTEND:{_iso(ev.end_time)}\r\n"
        f"SUMMARY:{(ev.subject or '').replace('\n',' ')}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def _contact_to_vcard(c: Contact) -> str:
    fn = c.display_name or ""
    email = c.email_address_1 or ""
    return (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        f"UID:CONTACT_{c.id}@local\r\n"
        f"FN:{fn}\r\n"
        f"EMAIL;TYPE=INTERNET:{email}\r\n"
        "END:VCARD\r\n"
    )


# CardDAV collection (address book)
@router.get("/carddav/addressbook/", name="carddav-collection")
async def carddav_collection(db: Session = Depends(get_db)):
    contacts: List[Contact] = db.query(Contact).limit(50).all()
    body = "".join(_contact_to_vcard(c) for c in contacts)
    return Response(content=body, media_type="text/vcard")


# Well-known discovery endpoints so clients can find the collections
@router.get("/.well-known/carddav")
async def well_known_carddav():
    # Minimal redirect-like hint using 301 would need RedirectResponse, but to keep simple
    return Response(status_code=200, content="/carddav/addressbook/", media_type="text/plain")


@router.get("/.well-known/caldav")
async def well_known_caldav():
    return Response(status_code=200, content="/caldav/calendar/", media_type="text/plain")


# CardDAV single resource
@router.get("/carddav/addressbook/{uid}.vcf")
async def carddav_item(uid: str, db: Session = Depends(get_db)):
    if uid.startswith("CONTACT_"):
        cid = uid.split("_", 1)[1].split("@", 1)[0]
        contact = db.get(Contact, int(cid))
        if contact:
            return Response(content=_contact_to_vcard(contact), media_type="text/vcard")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


# CalDAV calendar collection
@router.get("/caldav/calendar/")
async def caldav_collection(db: Session = Depends(get_db)):
    events: List[CalendarEvent] = (
        db.query(CalendarEvent).order_by(CalendarEvent.start_time.desc()).limit(50).all()
    )
    body = "".join(_event_to_ical(e) for e in events)
    return Response(content=body, media_type="text/calendar")


# CalDAV single resource
@router.get("/caldav/calendar/{uid}.ics")
async def caldav_item(uid: str, db: Session = Depends(get_db)):
    if uid.startswith("CAL_"):
        eid = uid.split("_", 1)[1].split("@", 1)[0]
        ev = db.get(CalendarEvent, int(eid))
        if ev:
            return Response(content=_event_to_ical(ev), media_type="text/calendar")
    return Response(status_code=status.HTTP_404_NOT_FOUND)
