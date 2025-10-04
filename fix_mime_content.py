#!/usr/bin/env python3
"""
Fix missing MIME content for existing emails in the database.
This script will populate the mime_content field for emails that have it as NULL.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db, Email
from activesync.wbxml_builder import _build_mime_message

def fix_mime_content():
    """Fix missing MIME content for existing emails."""
    db = next(get_db())
    
    # Find emails with missing MIME content
    emails_without_mime = db.query(Email).filter(
        (Email.mime_content.is_(None)) | (Email.mime_content == '')
    ).all()
    
    print(f"Found {len(emails_without_mime)} emails without MIME content")
    
    for email in emails_without_mime:
        try:
            # Build MIME content from existing body and body_html
            em_dict = {
                'subject': email.subject or '',
                'from': email.external_sender or 'unknown@example.com',
                'to': 'yonatan@shtrum.com',  # Default recipient
                'created_at': email.created_at,
                'body': email.body or '',
                'body_html': email.body_html or ''
            }
            
            mime_bytes = _build_mime_message(em_dict, em_dict['body_html'], em_dict['body'])
            # Store MIME content as base64 encoded string for ActiveSync compatibility
            import base64
            mime_content = base64.b64encode(mime_bytes).decode('ascii')
            
            # Update the email record
            email.mime_content = mime_content
            email.mime_content_type = 'multipart/alternative'
            
            print(f"Fixed MIME content for email ID {email.id}: {email.subject}")
            
        except Exception as e:
            print(f"Error fixing email ID {email.id}: {e}")
    
    # Commit all changes
    try:
        db.commit()
        print(f"Successfully updated {len(emails_without_mime)} emails with MIME content")
    except Exception as e:
        print(f"Error committing changes: {e}")
        db.rollback()

if __name__ == "__main__":
    fix_mime_content()
