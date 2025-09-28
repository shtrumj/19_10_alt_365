from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db, User
from ..auth import get_current_user_from_cookie
from ..email_service import EmailService
from ..models import EmailCreate
from ..language import get_language, get_translation, get_direction, get_all_translations
from typing import Optional, Union

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
        **kwargs
    }
    return context

@router.get("/", response_class=HTMLResponse)
def owa_home(request: Request, current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie)):
    """OWA Home page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("owa/home.html", get_template_context(request, user=current_user))

@router.get("/inbox", response_class=HTMLResponse)
def owa_inbox(
    request: Request,
    folder: str = "inbox",
    limit: int = 50,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """OWA Inbox page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    email_service = EmailService(db)
    emails = email_service.get_user_emails(current_user.id, folder, limit)
    
    return templates.TemplateResponse("owa/inbox.html", get_template_context(
        request, 
        user=current_user, 
        emails=emails, 
        folder=folder
    ))

@router.get("/compose", response_class=HTMLResponse)
def owa_compose(request: Request, current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie)):
    """OWA Compose email page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return templates.TemplateResponse("owa/compose.html", get_template_context(request, user=current_user))

@router.get("/email/{email_id}", response_class=HTMLResponse)
def owa_view_email(
    email_id: int,
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """OWA View email page"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    email_service = EmailService(db)
    email = email_service.get_email_by_id(email_id, current_user.id)
    
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Mark as read if it's an inbox email
    if email.recipient_id == current_user.id and not email.is_read:
        email_service.mark_as_read(email_id, current_user.id)
    
    return templates.TemplateResponse("owa/email.html", get_template_context(
        request, 
        user=current_user, 
        email=email
    ))

@router.post("/send", response_class=HTMLResponse)
async def owa_send_email(
    request: Request,
    current_user: Union[User, RedirectResponse] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Send email from OWA"""
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    form_data = await request.form()
    
    email_data = EmailCreate(
        subject=form_data.get("subject", ""),
        body=form_data.get("body", ""),
        recipient_email=form_data.get("recipient_email", "")
    )
    
    email_service = EmailService(db)
    try:
        email_service.send_email(email_data, current_user.id)
        return templates.TemplateResponse("owa/success.html", get_template_context(
            request, 
            user=current_user, 
            message="Email sent successfully"
        ))
    except Exception as e:
        return templates.TemplateResponse("owa/error.html", get_template_context(
            request, 
            user=current_user, 
            error=str(e)
        ))
