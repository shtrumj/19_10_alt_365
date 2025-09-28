"""
Email parsing utilities for displaying email content properly
"""
import email
import base64
import quopri
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

def parse_email_content(raw_email_body):
    """
    Parse raw email content and extract the readable message body
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🔍 Starting email parsing...")
        logger.debug(f"Raw email length: {len(raw_email_body)} characters")
        logger.debug(f"Raw email preview: {raw_email_body[:200]}...")
        
        # First try to find actual content in the raw text (simpler approach)
        logger.info("📝 Attempting raw text extraction...")
        content = extract_content_from_raw(raw_email_body)
        logger.info(f"Raw extraction result: '{content}' (length: {len(content)})")
        
        if content and len(content.strip()) > 0:
            logger.info("✅ Raw extraction successful!")
            return content.strip()
        
        # If that fails, try parsing as proper email
        logger.info("📧 Attempting proper email parsing...")
        msg = email.message_from_string(raw_email_body)
        content = extract_main_content(msg)
        logger.info(f"Email parsing result: '{content}' (length: {len(content)})")
        
        if content and len(content.strip()) > 0:
            logger.info("✅ Email parsing successful!")
            return content.strip()
        
        # Fallback to basic cleaning
        logger.info("🧹 Attempting basic cleaning...")
        cleaned = clean_email_content(raw_email_body)
        logger.info(f"Basic cleaning result: '{cleaned}' (length: {len(cleaned)})")
        return cleaned
        
    except Exception as e:
        logger.error(f"❌ Error parsing email: {e}")
        logger.exception("Full traceback:")
        # Fallback to raw content with basic cleaning
        return clean_email_content(raw_email_body)

def extract_content_from_raw(raw_email):
    """
    Extract content directly from raw email text by looking for actual message parts
    """
    import logging
    logger = logging.getLogger(__name__)
    
    lines = raw_email.split('\n')
    content_lines = []
    in_content_section = False
    
    logger.debug(f"Processing {len(lines)} lines from raw email")
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Look for the start of actual content sections
        if ('Content-Type: text/plain' in line or 
            'Content-Type: text/html' in line or
            (line.startswith('--') and 'boundary' in raw_email)):
            logger.debug(f"Found content section start at line {i}: {line}")
            in_content_section = True
            continue
            
        # Look for the end of content sections
        if line.startswith('--') and in_content_section:
            logger.debug(f"Found content section end at line {i}: {line}")
            in_content_section = False
            continue
            
        # Only process lines when we're in a content section
        if in_content_section and line:
            logger.debug(f"Processing content line {i}: '{line}'")
            # Skip headers and encoded content
            if (not line.startswith(('Content-Type:', 'Content-Transfer-Encoding:', 'From:', 'To:', 'Subject:', 'Date:')) and
                not re.match(r'^[A-Za-z0-9+/]{20,}={0,2}$', line) and
                not re.match(r'^[A-Za-z0-9+/]{20,}$', line) and
                (not line.startswith('<') or line.startswith('<div') or line.startswith('<p') or line.startswith('<span'))):
                
                # This looks like actual content
                if len(line) > 2 and len(line) < 200:
                    logger.debug(f"Adding content line: '{line}'")
                    content_lines.append(line)
    
    logger.info(f"Found {len(content_lines)} content lines in sections")
    
    # If we didn't find content in sections, look for simple text patterns
    if not content_lines:
        logger.info("No content found in sections, trying simple text patterns...")
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for simple text that's not headers or encoded
            if (line and 
                len(line) > 2 and len(line) < 100 and
                not line.startswith(('From:', 'To:', 'Subject:', 'Date:', 'Received:', 'DKIM-', 'X-', 'MIME-', 'Content-', 'Message-ID:', 'References:', 'In-Reply-To:')) and
                not line.startswith('(') and
                not line.startswith('by ') and
                not line.startswith('for ') and
                not re.match(r'^[A-Za-z0-9+/]{10,}={0,2}$', line) and
                not re.match(r'^[A-Za-z0-9+/]{10,}$', line) and
                (not any(char in line for char in ['=', '+', '/']) or line.count('=') < 3)):
                logger.debug(f"Adding simple text line {i}: '{line}'")
                content_lines.append(line)
    
    result = '\n'.join(content_lines)
    logger.info(f"Final extraction result: '{result}' (length: {len(result)})")
    return result

def extract_main_content(msg):
    """
    Extract the main readable content from an email message
    """
    content = ""
    
    if msg.is_multipart():
        # Handle multipart messages - look for actual content parts
        for part in msg.walk():
            content_type = part.get_content_type()
            
            # Skip multipart containers and attachments
            if content_type.startswith('multipart/'):
                continue
                
            # Look for text content
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content = decode_payload(payload, part.get_content_charset())
                    # Only use if it's actual content (not headers or encoded data)
                    if is_actual_content(decoded_content):
                        content = decoded_content
                        break
            elif content_type == "text/html" and not content:
                # Use HTML as fallback if no plain text found
                payload = part.get_payload(decode=True)
                if payload:
                    html_content = decode_payload(payload, part.get_content_charset())
                    if is_actual_content(html_content):
                        content = html_to_text(html_content)
                        break
    else:
        # Single part message
        payload = msg.get_payload(decode=True)
        if payload:
            content = decode_payload(payload, msg.get_content_charset())
    
    return content

def is_actual_content(text):
    """
    Check if text is actual message content (not headers or encoded data)
    """
    if not text or len(text.strip()) < 3:
        return False
    
    # Skip if it looks like headers
    if any(text.strip().startswith(header) for header in [
        'From:', 'To:', 'Subject:', 'Date:', 'Received:', 'DKIM-', 'X-', 
        'MIME-', 'Content-', 'Message-ID:', 'References:', 'In-Reply-To:',
        'Return-Path:', 'Delivered-To:', 'Authentication-Results:'
    ]):
        return False
    
    # Skip if it's mostly encoded data (base64, quoted-printable patterns)
    if len(text) > 50 and (text.count('=') > len(text) * 0.1 or 
                          text.count('/') > len(text) * 0.1 or
                          text.count('+') > len(text) * 0.1):
        return False
    
    # Skip if it's mostly special characters or very short
    if len(text.strip()) < 5:
        return False
        
    return True

def decode_payload(payload, charset=None):
    """
    Decode email payload with proper charset handling
    """
    try:
        if isinstance(payload, bytes):
            if charset:
                return payload.decode(charset, errors='ignore')
            else:
                return payload.decode('utf-8', errors='ignore')
        else:
            return str(payload)
    except Exception:
        return str(payload)

def clean_email_content(content):
    """
    Clean up email content by removing headers and encoded parts
    """
    if not content:
        return ""
    
    # Split into lines for processing
    lines = content.split('\n')
    cleaned_lines = []
    
    # Skip headers and look for actual content
    skip_headers = True
    found_content = False
    
    for line in lines:
        line = line.strip()
        
        # Stop skipping headers when we find actual content
        if skip_headers:
            # Check if this line looks like actual content (not headers)
            if (line and 
                not line.startswith(('From:', 'To:', 'Subject:', 'Date:', 'Received:', 'DKIM-', 'X-', 'MIME-', 'Content-', 'Message-ID:', 'References:', 'In-Reply-To:', 'Return-Path:', 'Delivered-To:', 'Authentication-Results:')) and
                not line.startswith('(') and  # Skip lines like "(using TLS with cipher...)"
                not line.startswith('by ') and  # Skip "by mail-wr1-f45.google.com..."
                not line.startswith('for ') and  # Skip "for ; Sun, 28 Sep..."
                not line.startswith('--') and  # Skip MIME boundaries
                not re.match(r'^[A-Za-z0-9+/]{20,}={0,2}$', line) and  # Skip base64
                not re.match(r'^[A-Za-z0-9+/]{20,}$', line) and  # Skip encoded content
                len(line) > 2):  # Must be more than 2 characters
                skip_headers = False
                found_content = True
        
        # Add content lines
        if not skip_headers:
            # Skip empty lines at the beginning
            if not found_content and not line:
                continue
            found_content = True
            cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Remove any remaining encoded content
    content = re.sub(r'^[A-Za-z0-9+/]{20,}={0,2}$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^[A-Za-z0-9+/]{20,}$', '', content, flags=re.MULTILINE)
    
    # Remove very long lines that look like encoded content
    content = re.sub(r'^.{100,}$', '', content, flags=re.MULTILINE)
    
    # Clean up multiple empty lines
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    # Remove trailing whitespace
    content = content.strip()
    
    return content

def html_to_text(html_content):
    """
    Basic HTML to text conversion
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_content)
    
    # Decode HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    
    return text

def get_email_preview(email_body, max_length=100):
    """
    Get a clean preview of the email content
    """
    content = parse_email_content(email_body)
    
    # Truncate if too long
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    return content
