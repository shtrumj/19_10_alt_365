from datetime import datetime
from typing import List

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.orm import Session

from ..auth import authenticate_user
from ..database import CalendarEvent, Contact, get_db

router = APIRouter(prefix="", tags=["caldav-carddav"])  # mounted directly


async def _basic_auth(request: Request, db: Session) -> str | None:
    """Return authenticated user's email, or None if not authenticated."""
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return None
        import base64

        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
        user = authenticate_user(db, username, password)
        return user.email if user else None
    except Exception:
        return None


def _iso(dt: datetime | None) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ") if dt else ""


def _event_to_ical(ev: CalendarEvent) -> str:
    subject_clean = (ev.subject or "").replace("\n", " ")
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//365-Email-System//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:CAL_{ev.id}@local\r\n"
        f"DTSTAMP:{_iso(ev.created_at)}\r\n"
        f"DTSTART:{_iso(ev.start_time)}\r\n"
        f"DTEND:{_iso(ev.end_time)}\r\n"
        f"SUMMARY:{subject_clean}\r\n"
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
async def carddav_collection(request: Request):
    db: Session = next(get_db())
    contacts: List[Contact] = db.query(Contact).limit(50).all()
    body = "".join(_contact_to_vcard(c) for c in contacts)
    return Response(content=body, media_type="text/vcard")


# CardDAV WebDAV discovery for Thunderbird
@router.options("/carddav/addressbook/")
async def carddav_options():
    return Response(
        status_code=204,
        headers={
            "DAV": "1, addressbook",
            "Allow": "OPTIONS, PROPFIND, REPORT, GET",
        },
    )


@router.api_route("/carddav/addressbook/", methods=["PROPFIND"])
async def carddav_propfind(request: Request):
    # Minimal multistatus describing the addressbook collection
    xml = (
        """
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/carddav/addressbook/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype>
          <d:collection/>
          <card:addressbook/>
        </d:resourcetype>
        <d:displayname>Address Book</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
 </d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/carddav/addressbook/", methods=["REPORT"])
async def carddav_report(request: Request):
    db: Session = next(get_db())
    # Return all contacts inline as address-data in a multistatus
    contacts = db.query(Contact).limit(50).all()
    responses = []
    for c in contacts:
        uid = f"CONTACT_{c.id}.vcf"
        vcard = _contact_to_vcard(c)
        # Simple, weak ETag based on id
        etag = f'"{c.id}"'
        responses.append(
            f"<d:response><d:href>/carddav/addressbook/{uid}</d:href>"
            f"<d:propstat><d:prop>"
            f"<d:getetag>{etag}</d:getetag>"
            f'<card:address-data xmlns:card="urn:ietf:params:xml:ns:carddav">{vcard}</card:address-data>'
            f"</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
        + "".join(responses)
        + "</d:multistatus>"
    )
    return Response(content=body, media_type="application/xml", status_code=207)


# Well-known discovery endpoints so clients can find the collections
@router.get("/.well-known/carddav")
async def well_known_carddav():
    return Response(status_code=301, headers={"Location": "/carddav/addressbook/"})


@router.get("/.well-known/caldav")
async def well_known_caldav():
    return Response(status_code=301, headers={"Location": "/caldav/calendar/"})


# CardDAV single resource
@router.get("/carddav/addressbook/{uid}.vcf")
async def carddav_item(uid: str, request: Request):
    db: Session = next(get_db())
    if uid.startswith("CONTACT_"):
        cid = uid.split("_", 1)[1].split("@", 1)[0]
        contact = db.get(Contact, int(cid))
        if contact:
            return Response(content=_contact_to_vcard(contact), media_type="text/vcard")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


# CalDAV calendar collection
@router.get("/caldav/calendar/")
async def caldav_collection(request: Request):
    db: Session = next(get_db())
    events: List[CalendarEvent] = (
        db.query(CalendarEvent)
        .order_by(CalendarEvent.start_time.desc())
        .limit(50)
        .all()
    )
    body = "".join(_event_to_ical(e) for e in events)
    return Response(content=body, media_type="text/calendar")


# CalDAV single resource
@router.get("/caldav/calendar/{uid}.ics")
async def caldav_item(uid: str, request: Request):
    db: Session = next(get_db())
    if uid.startswith("CAL_"):
        eid = uid.split("_", 1)[1].split("@", 1)[0]
        ev = db.get(CalendarEvent, int(eid))
        if ev:
            return Response(content=_event_to_ical(ev), media_type="text/calendar")
    return Response(status_code=status.HTTP_404_NOT_FOUND)


# CalDAV WebDAV discovery
@router.options("/caldav/calendar/")
async def caldav_options():
    return Response(
        status_code=204,
        headers={
            "DAV": "1, 2, calendar-access",
            "Allow": "OPTIONS, PROPFIND, REPORT, GET",
        },
    )


@router.api_route("/caldav/", methods=["PROPFIND"])
async def caldav_home_propfind(request: Request):
    db: Session = next(get_db())
    # Advertise the calendar-home-set and current-user-principal
    user_email = await _basic_auth(request, db)
    home = "/caldav/calendar/" if not user_email else f"/caldav/{user_email}/calendar/"
    principal = (
        "/principals/users/default/"
        if not user_email
        else f"/principals/users/{user_email}/"
    )
    xml = (
        """
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/caldav/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
        <cal:calendar-home-set><d:href>"""
        + home
        + """</d:href></cal:calendar-home-set>
        <d:current-user-principal><d:href>"""
        + principal
        + """</d:href></d:current-user-principal>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/carddav/", methods=["PROPFIND"])
async def carddav_home_propfind(request: Request):
    db: Session = next(get_db())
    # Advertise the addressbook-home-set and current-user-principal
    user_email = await _basic_auth(request, db)
    home = (
        "/carddav/addressbook/"
        if not user_email
        else f"/carddav/{user_email}/addressbook/"
    )
    principal = (
        "/principals/users/default/"
        if not user_email
        else f"/principals/users/{user_email}/"
    )
    xml = (
        """
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/carddav/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
        <card:addressbook-home-set><d:href>"""
        + home
        + """</d:href></card:addressbook-home-set>
        <d:current-user-principal><d:href>"""
        + principal
        + """</d:href></d:current-user-principal>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.options("/caldav/")
async def caldav_root_options():
    return Response(
        status_code=204,
        headers={"DAV": "1, 2, calendar-access", "Allow": "OPTIONS, PROPFIND"},
    )


@router.options("/carddav/")
async def carddav_root_options():
    return Response(
        status_code=204, headers={"DAV": "1, addressbook", "Allow": "OPTIONS, PROPFIND"}
    )


@router.api_route("/principals/users/{user_email}/", methods=["PROPFIND"])
async def dav_principal(user_email: str):
    xml = (
        f"""
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/principals/users/{user_email}/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:principal/></d:resourcetype>
        <cal:calendar-home-set><d:href>/caldav/{user_email}/calendar/</d:href></cal:calendar-home-set>
        <card:addressbook-home-set><d:href>/carddav/{user_email}/addressbook/</d:href></card:addressbook-home-set>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/carddav/{user_email}/addressbook/", methods=["PROPFIND"])
async def carddav_user_addressbook_propfind(user_email: str):
    xml = (
        f"""
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/carddav/{user_email}/addressbook/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/><card:addressbook/></d:resourcetype>
        <d:displayname>Address Book</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/caldav/{user_email}/calendar/", methods=["PROPFIND"])
async def caldav_user_calendar_propfind(user_email: str):
    xml = (
        f"""
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/caldav/{user_email}/calendar/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
        <d:displayname>Calendar</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/caldav/calendar/", methods=["PROPFIND"])
async def caldav_propfind(request: Request):
    # Describe the calendar collection
    xml = (
        """
<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/caldav/calendar/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/><cal:calendar/></d:resourcetype>
        <d:displayname>Calendar</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    ).strip()
    return Response(content=xml, media_type="application/xml", status_code=207)


@router.api_route("/caldav/calendar/", methods=["REPORT"])
async def caldav_report(request: Request):
    db: Session = next(get_db())
    # Return all events as calendar-data in a multistatus
    events: List[CalendarEvent] = (
        db.query(CalendarEvent)
        .order_by(CalendarEvent.start_time.desc())
        .limit(50)
        .all()
    )
    responses = []
    for e in events:
        uid = f"CAL_{e.id}.ics"
        ical = _event_to_ical(e)
        etag = f'"{e.id}"'
        responses.append(
            f"<d:response><d:href>/caldav/calendar/{uid}</d:href>"
            f"<d:propstat><d:prop>"
            f"<d:getetag>{etag}</d:getetag>"
            f'<cal:calendar-data xmlns:cal="urn:ietf:params:xml:ns:caldav">{ical}</cal:calendar-data>'
            f"</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        )
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
        + "".join(responses)
        + "</d:multistatus>"
    )
    return Response(content=body, media_type="application/xml", status_code=207)
