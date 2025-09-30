import os
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..auth import get_current_user_from_cookie
from ..config import settings
from ..database import Email, User, get_db
from ..diagnostic_logger import outlook_health
from ..email_delivery import email_delivery
from ..email_parser import get_email_preview, parse_email_content
from ..email_queue import QueuedEmail
from ..email_service import EmailService
from ..language import (
    get_all_translations,
    get_direction,
    get_language,
    get_translation,
)
from ..models import EmailCreate, EmailSummary
from ..queue_processor import queue_processor
from ..smtp_server import start_smtp_server, stop_smtp_server

router = APIRouter(prefix="/owa", tags=["owa"])
templates = Jinja2Templates(directory="templates")


def get_template_context(request: Request, **kwargs):
    """Get template context with language support"""
    context = {
        "request": request,
        "get_language": get_language,
        "get_translation": get_translation,
        "get_direction": get_direction,
        "get_all_translations": get_all_translations,
        "parse_email_content": parse_email_content,
        "get_email_preview": get_email_preview,
        "hostname": settings.HOSTNAME,  # Hostname for WebSocket connections
        **kwargs,
    }
    return context


@router.get("/", response_class=HTMLResponse)
@router.get("/owa", response_class=HTMLResponse)
def owa_home(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """OWA Home page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        "owa/home.html", get_template_context(request, user=current_user)
    )


@router.get("/inbox", response_class=HTMLResponse)
def owa_inbox(
    request: Request,
    folder: str = "inbox",
    limit: int = 50,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """OWA Inbox page"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    email_service = EmailService(db)
    emails = email_service.get_user_emails(current_user.id, folder, limit)

    return templates.TemplateResponse(
        "owa/inbox.html",
        get_template_context(request, user=current_user, emails=emails, folder=folder),
    )


@router.get("/compose", response_class=HTMLResponse)
def owa_compose(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """OWA Compose email page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse(
        "owa/compose.html", get_template_context(request, user=current_user)
    )


@router.get("/admin", response_class=HTMLResponse)
def owa_admin_dashboard(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    from ..email_queue import EmailQueue

    queue = EmailQueue()
    stats = queue.get_queue_stats()
    return templates.TemplateResponse(
        "owa/admin.html",
        get_template_context(request, user=current_user, queue_stats=stats),
    )


@router.get("/admin/queues", response_class=HTMLResponse)
def owa_admin_queues(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    # Queue stats and listings
    from ..database import Email
    from ..email_queue import EmailQueue, QueuedEmail

    queue = EmailQueue()
    stats = queue.get_queue_stats()
    # Recent outbound (queued) emails
    queued_emails = (
        db.query(QueuedEmail).order_by(QueuedEmail.created_at.desc()).limit(20).all()
    )
    # Recent inbound (external) emails stored
    inbound_emails = (
        db.query(Email)
        .filter(Email.is_external == True)
        .order_by(Email.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        "owa/queues.html",
        get_template_context(
            request,
            user=current_user,
            queue_stats=stats,
            queued_emails=queued_emails,
            inbound_emails=inbound_emails,
        ),
    )


@router.get("/admin/audit", response_class=HTMLResponse)
def owa_admin_audit(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse(
        "owa/audit.html", get_template_context(request, user=current_user)
    )


@router.get("/admin/smtp-logs", response_class=HTMLResponse)
def owa_admin_smtp_logs(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """Admin page for incoming SMTP logs troubleshooting."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse(
        "owa/smtp_logs.html", get_template_context(request, user=current_user)
    )


@router.get("/admin/smtp-logs/data")
def owa_admin_smtp_logs_data(
    request: Request,
    log: str = "internal_smtp",
    q: Optional[str] = None,
    match_only: bool = True,
    max_lines: int = 300,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """Return tail of selected SMTP-related log with optional filtering.

    Params:
      - log: internal_smtp | smtp_errors | email_processing
      - q: optional substring (case-insensitive)
      - match_only: if true, only include matching lines when q is set
      - max_lines: number of tail lines to consider
    """
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    logs_dir = os.environ.get("LOGS_DIR", "./logs")
    log_map = {
        "internal_smtp": "internal_smtp.log",
        "smtp_errors": "smtp_errors.log",
        "email_processing": "email_processing.log",
    }
    filename = log_map.get(log, "internal_smtp.log")
    full_path = os.path.join(logs_dir, filename)

    lines = []
    try:
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
                tail_lines = all_lines[
                    -max(1, min(max_lines, 2000)) :
                ]  # cap to prevent huge payloads
                if q:
                    query = q.lower()
                    if match_only:
                        lines = [ln for ln in tail_lines if query in ln.lower()]
                    else:
                        # include all tail lines but mark matches client-side
                        lines = tail_lines
                else:
                    lines = tail_lines
        else:
            lines = []
    except Exception:
        lines = []

    # Trim trailing newlines for JSON cleanliness, client will join with \n
    clean = [ln.rstrip("\n") for ln in lines]
    return {
        "file": filename,
        "count": len(clean),
        "max": max_lines,
        "query": q or "",
        "match_only": match_only,
        "lines": clean,
    }


@router.post("/admin/smtp-logs/clear")
def owa_admin_smtp_logs_clear(
    request: Request,
    log: str = "internal_smtp",
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """Clear the selected SMTP log file (truncate)."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    logs_dir = os.environ.get("LOGS_DIR", "./logs")
    log_map = {
        "internal_smtp": "internal_smtp.log",
        "smtp_errors": "smtp_errors.log",
        "email_processing": "email_processing.log",
    }
    filename = log_map.get(log, "internal_smtp.log")
    full_path = os.path.join(logs_dir, filename)
    try:
        # Truncate file if exists, else create empty
        with open(full_path, "w", encoding="utf-8") as f:
            f.write("")
        # Reopen log file handlers to ensure writes continue after truncation
        try:
            from ..smtp_logger import smtp_logger

            smtp_logger.reopen_files()
        except Exception:
            pass
        return {"file": filename, "cleared": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/audit/emails")
def owa_admin_audit_emails(
    request: Request,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    window: str = "1h",
    limit: int = 100,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Query recently received emails (inbound via SMTP) with filters.

    Params:
      - sender: filter by external sender contains
      - recipient: filter by recipient email contains
      - window: one of 5m,15m,1h,6h,24h,7d,30d
      - limit: max rows
    """
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.utcnow()
    window_map = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = window_map.get(window, timedelta(hours=1))
    since = now - delta

    # Base query: inbound emails created recently
    q = db.query(Email).filter(
        Email.created_at >= since, Email.is_deleted == False, Email.is_external == True
    )

    if sender:
        q = q.filter(Email.external_sender.ilike(f"%{sender}%"))

    if recipient:
        # Match recipient user email when available, otherwise external_recipient (unlikely for inbound)
        q = q.filter(
            or_(
                Email.external_recipient.ilike(f"%{recipient}%"),
                Email.recipient.has(User.email.ilike(f"%{recipient}%")),
            )
        )

    emails = q.order_by(Email.created_at.desc()).limit(max(1, min(limit, 500))).all()

    # Convert to simple dicts
    results = []
    for e in emails:
        summary = EmailSummary.from_email(e)
        results.append(
            {
                "id": summary.id,
                "subject": summary.subject,
                "sender_email": summary.sender_email,
                "recipient_email": summary.recipient_email,
                "is_read": summary.is_read,
                "created_at": summary.created_at.isoformat() + "Z",
            }
        )

    return {
        "count": len(results),
        "window": window,
        "since": since.isoformat() + "Z",
        "items": results,
    }


@router.get("/admin/gal")
def owa_admin_gal_preview(
    request: Request,
    q: Optional[str] = None,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    from ..database import User as DBUser

    patt = f"%{(q or '').lower()}%"
    users = (
        db.query(DBUser)
        .filter(
            (DBUser.email.ilike(patt))
            | (DBUser.username.ilike(patt))
            | (DBUser.full_name.ilike(patt))
        )
        .order_by(DBUser.full_name.asc())
        .limit(50)
        .all()
    )
    return [
        {"id": u.id, "display_name": u.full_name or u.username, "email": u.email}
        for u in users
    ]


@router.get("/admin/outlook-health", response_class=HTMLResponse)
async def outlook_health_dashboard(
    request: Request, current_user: User = Depends(get_current_user_from_cookie)
):
    """Outlook connection health dashboard"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Pass the full context, including the translation function `_`
    context = get_template_context(
        request, user=current_user, title="Outlook Health Monitor"
    )
    return templates.TemplateResponse("owa/outlook_health.html", context)


@router.get("/admin/outlook-health/data")
async def outlook_health_data(
    request: Request, current_user: User = Depends(get_current_user_from_cookie)
):
    """Get real-time Outlook health data"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")

    health_summary = outlook_health.get_health_summary()

    # Read recent health issues
    health_issues = []
    try:
        logs_dir = os.getenv("LOGS_DIR", "logs")
        health_issues_file = os.path.join(logs_dir, "outlook", "health_issues.log")
        if os.path.exists(health_issues_file):
            with open(health_issues_file, "r") as f:
                lines = f.readlines()[-50:]  # Last 50 issues
                for line in lines:
                    try:
                        import json

                        issue = json.loads(line.strip())
                        health_issues.append(issue)
                    except:
                        continue
    except Exception as e:
        pass

    # Get connection statistics
    connection_stats = {
        "active_connections": health_summary.get("active_connections", 0),
        "total_tracked": health_summary.get("total_tracked", 0),
        "recent_issues": len(health_issues),
        "critical_issues": len(
            [i for i in health_issues if i.get("severity") == "high"]
        ),
    }

    return {
        "health_summary": health_summary,
        "health_issues": health_issues,
        "connection_stats": connection_stats,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/admin/actions/smtp/start")
async def owa_admin_action_smtp_start(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await start_smtp_server()
    return {"status": "started"}


@router.post("/admin/actions/smtp/stop")
async def owa_admin_action_smtp_stop(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await stop_smtp_server()
    return {"status": "stopped"}


@router.post("/admin/actions/smtp/restart")
async def owa_admin_action_smtp_restart(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await stop_smtp_server()
    await start_smtp_server()
    return {"status": "restarted"}


@router.post("/admin/actions/queue/process")
async def owa_admin_action_queue_process(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await email_delivery.process_queue(db)
    return {"status": "processed"}


@router.post("/admin/actions/queue/flush")
async def owa_admin_action_queue_flush(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Fast-forward retries and process queue until empty or max cycles."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Fast-forward all RETRY items to be eligible now
    now = datetime.utcnow()
    try:
        updated = (
            db.query(QueuedEmail)
            .filter(QueuedEmail.status == "retry")
            .update({QueuedEmail.next_retry_at: now}, synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        updated = 0

    cycles = 0
    max_cycles = 5
    while cycles < max_cycles:
        cycles += 1
        await email_delivery.process_queue(db)
        # Check if more work remains
        pending = db.query(QueuedEmail).filter(QueuedEmail.status == "pending").count()
        retry_ready = (
            db.query(QueuedEmail)
            .filter(QueuedEmail.status == "retry", QueuedEmail.next_retry_at <= now)
            .count()
        )
        if pending == 0 and retry_ready == 0:
            break
    return {"status": "flushed", "fast_forwarded": updated, "cycles": cycles}


@router.post("/admin/actions/queue/start")
async def owa_admin_action_queue_start(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await queue_processor.start()
    return {"status": "queue_processor_started"}


@router.post("/admin/actions/queue/stop")
async def owa_admin_action_queue_stop(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await queue_processor.stop()
    return {"status": "queue_processor_stopped"}


@router.post("/admin/actions/queue/restart")
async def owa_admin_action_queue_restart(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    await queue_processor.stop()
    await queue_processor.start()
    return {"status": "queue_processor_restarted"}


@router.get("/admin/audit/logs")
def owa_admin_audit_logs(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
):
    """Return tail of SMTP logs for live audit (polling)."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    if not getattr(current_user, "admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")
    logs_dir = os.environ.get("LOGS_DIR", "./logs")

    def tail(path: str, max_lines: int = 200) -> str:
        try:
            full = os.path.join(logs_dir, path)
            if not os.path.exists(full):
                return ""
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception:
            return ""

    return {
        "internal_smtp": tail("internal_smtp.log", 250),
        "smtp_errors": tail("smtp_errors.log", 250),
        "email_processing": tail("email_processing.log", 200),
    }


@router.get("/email/{email_uuid}", response_class=HTMLResponse)
def owa_view_email(
    email_uuid: str,
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """OWA View email page"""
    import logging

    logger = logging.getLogger(__name__)

    if isinstance(current_user, RedirectResponse):
        return current_user

    logger.info(f"📧 Viewing email {email_uuid}")

    # Prefer lookup by UUID
    email = db.query(Email).filter(Email.uuid == email_uuid).first()
    # Fallback to numeric id passed as uuid
    if not email and email_uuid.isdigit():
        email_service = EmailService(db)
        email = email_service.get_email_by_id(int(email_uuid), current_user.id)

    if not email:
        logger.error(f"Email {email_uuid} not found")
        raise HTTPException(status_code=404, detail="Email not found")

    logger.info(f"Email subject: {email.subject}")
    logger.debug(f"Email body length: {len(email.body)}")
    logger.debug(f"Email body preview: {email.body[:200]}...")

    # Use body as-is; it may already contain parsed HTML from SMTP stage
    parsed_content = email.body or ""
    logger.info(f"Using stored email body for display (length: {len(parsed_content)})")

    # Mark as read if it's an inbox email
    if email.recipient_id == current_user.id and not email.is_read:
        EmailService(db).mark_as_read(email.id, current_user.id)

    # Add parsed content to email object for template
    email.parsed_content = parsed_content

    return templates.TemplateResponse(
        "owa/email.html", get_template_context(request, user=current_user, email=email)
    )


@router.get("/email/{email_uuid}/delete")
def owa_delete_email(
    email_uuid: str,
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Delete email by UUID (OWA-friendly redirect)."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    # resolve uuid to id owned by user (sender or recipient)
    email = db.query(Email).filter(Email.uuid == email_uuid).first()
    if not email:
        # fallback numeric id
        if email_uuid.isdigit():
            email = db.query(Email).filter(Email.id == int(email_uuid)).first()
    if email and (
        email.sender_id == current_user.id or email.recipient_id == current_user.id
    ):
        from ..email_service import EmailService

        EmailService(db).delete_email(email.id, current_user.id)
    return RedirectResponse(url="/owa/inbox", status_code=303)


@router.post("/send", response_class=HTMLResponse)
async def owa_send_email(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """Send email from OWA"""
    if isinstance(current_user, RedirectResponse):
        return current_user

    form_data = await request.form()

    email_data = EmailCreate(
        subject=form_data.get("subject", ""),
        body=form_data.get("body", ""),
        recipient_email=form_data.get("recipient_email", ""),
    )

    email_service = EmailService(db)
    try:
        email_service.send_email(email_data, current_user.id)
        return templates.TemplateResponse(
            "owa/success.html",
            get_template_context(
                request, user=current_user, message="Email sent successfully"
            ),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "owa/error.html",
            get_template_context(request, user=current_user, error=str(e)),
        )
