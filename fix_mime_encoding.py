#!/usr/bin/env python3
"""
Fix MIME content encoding for existing emails in the database.
This script will re-encode MIME content that was stored as UTF-8 strings instead of base64.
"""

import sys
import os
import base64
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db, Email

def fix_mime_encoding():
    """Fix MIME content encoding for existing emails."""
    db = next(get_db())
    
    # Find emails with MIME content that might be incorrectly encoded
    emails_with_mime = db.query(Email).filter(
        Email.mime_content.isnot(None),
        Email.mime_content != ''
    ).all()
    
    print(f"Found {len(emails_with_mime)} emails with MIME content")
    
    fixed_count = 0
    for email in emails_with_mime:
        try:
            mime_content = email.mime_content
            
            # Check if it's already base64 encoded
            try:
                # Try to decode as base64
                decoded = base64.b64decode(mime_content)
                # If successful, check if it looks like MIME content
                if b'Content-Type:' in decoded or b'MIME-Version:' in decoded:
                    print(f"Email ID {email.id} already has base64 encoded MIME content")
                    continue
            except:
                pass
            
            # If we get here, it's not base64 encoded, so re-encode it
            print(f"Fixing MIME encoding for email ID {email.id}: {email.subject}")
            
            # Re-encode the MIME content as base64
            mime_bytes = mime_content.encode('utf-8')
            mime_content_base64 = base64.b64encode(mime_bytes).decode('ascii')
            
            # Update the email record
            email.mime_content = mime_content_base64
            fixed_count += 1
            
        except Exception as e:
            print(f"Error fixing email ID {email.id}: {e}")
    
    # Commit all changes
    try:
        db.commit()
        print(f"Successfully updated {fixed_count} emails with proper MIME encoding")
    except Exception as e:
        print(f"Error committing changes: {e}")
        db.rollback()

if __name__ == "__main__":
    fix_mime_encoding()
