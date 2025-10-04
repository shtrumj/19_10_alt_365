"""Utility functions for building MIME messages and rendering HTML bodies."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple
import html


def plain_to_html(plain: str) -> str:
    """Convert plain text into a simple HTML representation."""
    if not plain:
        return ""
    escaped = html.escape(plain)
    return escaped.replace("\n", "<br>\n")


def build_mime_message(
    subject: Optional[str],
    sender: Optional[str],
    recipient: Optional[str],
    plain_body: Optional[str],
    html_body: Optional[str] = None,
) -> Tuple[str, str]:
    """Compose a MIME message string and return it with its content type."""
    plain_body = plain_body or ""
    if html_body:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(plain_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        message = MIMEText(plain_body, "plain", "utf-8")

    if subject:
        message["Subject"] = subject
    if sender:
        message["From"] = sender
    if recipient:
        message["To"] = recipient

    return message.as_string(), message.get_content_type()
