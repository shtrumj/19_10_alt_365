"""
Debug endpoints for email parsing analysis
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db, Email
from ..auth import get_current_user_from_cookie
from ..email_parser import parse_email_content, get_email_preview
from ..logging_config import log_email_parsing_debug
from typing import Union
import logging

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger(__name__)

@router.get("/email/{email_id}/parse")
def debug_email_parsing(
    email_id: int,
    current_user: Union[dict, None] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Debug email parsing for a specific email"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    logger.info(f"🔍 Debug parsing email {email_id}")
    
    # Parse the email
    parsed_content = parse_email_content(email.body)
    
    # Log detailed debug information
    log_email_parsing_debug(email.body, parsed_content, "debug_endpoint")
    
    return JSONResponse({
        "email_id": email_id,
        "subject": email.subject,
        "raw_body_length": len(email.body),
        "raw_body_preview": email.body[:200] + "..." if len(email.body) > 200 else email.body,
        "parsed_content": parsed_content,
        "parsed_length": len(parsed_content),
        "preview": get_email_preview(email.body, 100)
    })

@router.get("/email/{email_id}/raw")
def debug_email_raw(
    email_id: int,
    current_user: Union[dict, None] = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Get raw email content for analysis"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return JSONResponse({
        "email_id": email_id,
        "subject": email.subject,
        "raw_body": email.body,
        "body_length": len(email.body)
    })

@router.get("/logs")
def debug_logs():
    """Get recent log files"""
    import os
    import glob
    
    log_files = []
    if os.path.exists('logs'):
        log_files = glob.glob('logs/*.log')
        log_files.sort(key=os.path.getmtime, reverse=True)
    
    return JSONResponse({
        "log_files": log_files,
        "logs_directory": "logs/"
    })

@router.get("/test-parsing")
def test_email_parsing():
    """Test email parsing with sample data"""
    sample_email = """From: test@example.com
To: user@example.com
Subject: Test Email
Date: 2025-09-28 12:00:00

Content-Type: multipart/alternative; boundary="test123"

--test123
Content-Type: text/plain; charset="UTF-8"

Hello World!

--test123
Content-Type: text/html; charset="UTF-8"

Hello World!

--test123--"""
    
    parsed = parse_email_content(sample_email)
    
    return JSONResponse({
        "sample_email": sample_email,
        "parsed_content": parsed,
        "success": "Hello World!" in parsed
    })

@router.get("/test-template")
def test_template_rendering():
    """Test template rendering with email parsing"""
    from fastapi.templating import Jinja2Templates
    from fastapi import Request
    
    templates = Jinja2Templates(directory="templates")
    
    # Sample email data
    sample_email = """From: shtrumj@gmail.com> SIZE=4458
To: yonatan@shtrum.com
Date: 2025-09-28 12:42:24
(using TLS with cipher ECDHE-RSA-AES128-GCM-SHA256 (128/128 bits))

Content-Type: multipart/alternative; boundary="test123"

--test123
Content-Type: text/plain; charset="UTF-8"

Bizzzbazzz

--test123
Content-Type: text/html; charset="UTF-8"

Bizzzbazzz

--test123--"""
    
    # Mock email object
    class MockEmail:
        def __init__(self, body):
            self.body = body
            self.id = 1
            self.subject = "Test Email"
            self.is_read = False
    
    email = MockEmail(sample_email)
    
    # Test template context
    context = {
        "request": None,
        "email": email,
        "parse_email_content": parse_email_content,
        "get_email_preview": get_email_preview
    }
    
    # Test template rendering
    try:
        template_content = "{{ parse_email_content(email.body)|replace('\n', '<br>')|safe }}"
        from jinja2 import Template
        template = Template(template_content)
        result = template.render(**context)
        
        return JSONResponse({
            "template_result": result,
            "success": "Bizzzbazzz" in result,
            "context_keys": list(context.keys())
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "success": False
        })
