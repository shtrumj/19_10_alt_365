import asyncio
import email
import html as html_unescape
import logging
import os
import re
import socket
import ssl
import threading
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Email, SessionLocal, User
from .email_parser import decode_payload, html_to_text, parse_mime_email
from .mime_utils import plain_to_html
from .smtp_logger import smtp_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_ssl_context():
    """Create SSL context for SMTP server"""
    try:
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Try to load certificates if they exist
        cert_file = os.path.join(os.path.dirname(__file__), "..", "ssl", "smtp.crt")
        key_file = os.path.join(os.path.dirname(__file__), "..", "ssl", "smtp.key")

        if os.path.exists(cert_file) and os.path.exists(key_file):
            context.load_cert_chain(cert_file, key_file)
            logger.info("🔒 SSL certificates loaded successfully")
        else:
            logger.warning("🔒 SSL certificates not found, using default context")

        return context
    except Exception as e:
        logger.error(f"🔒 Failed to create SSL context: {e}")
        return None


class EmailHandler:
    """Custom SMTP server for processing incoming emails using asyncio and socket with TLS support"""

    def __init__(self, ssl_context=None):
        self.db = SessionLocal()
        self.connection_count = 0
        self.ssl_context = ssl_context
        logger.info(
            "🔧 EmailHandler initialized with custom asyncio SMTP server (TLS support: {})".format(
                "enabled" if ssl_context else "disabled"
            )
        )

    async def handle_client(self, reader, writer):
        """Handle SMTP client connection"""
        self.connection_count += 1
        connection_id = f"conn_{self.connection_count}"
        peer = writer.get_extra_info("peername")

        logger.info(f"🔗 [{connection_id}] New connection from {peer}")

        try:
            # Send SMTP greeting
            writer.write(b"220 Python SMTP Server Ready\r\n")
            await writer.drain()

            # SMTP state
            mail_from = None
            rcpt_to = []
            data_mode = False
            data_buffer = []
            tls_started = False

            while True:
                # Read command
                line_bytes = await reader.readline()
                if not line_bytes:
                    break

                line_text = line_bytes.decode("utf-8", errors="ignore")

                if data_mode:
                    stripped = line_text.rstrip("\r\n")
                    if stripped == ".":
                        logger.info(f"🔗 [{connection_id}] End of data received")
                        data_content = "".join(data_buffer)

                        # Process the email
                        result = await self.process_email(
                            connection_id, peer, mail_from, rcpt_to, data_content
                        )

                        writer.write(f"{result}\r\n".encode())
                        await writer.drain()

                        # Reset for next email
                        mail_from = None
                        rcpt_to = []
                        data_mode = False
                        data_buffer = []
                    else:
                        data_buffer.append(line_text)
                    continue

                command = line_text.strip()
                logger.info(f"🔗 [{connection_id}] Command: {command}")

                if command.upper().startswith("EHLO") or command.upper().startswith(
                    "HELO"
                ):
                    # For now, don't advertise STARTTLS to avoid TLS issues
                    writer.write(
                        b"250-Hello\r\n250-SIZE 33554432\r\n250-8BITMIME\r\n250-SMTPUTF8\r\n250 HELP\r\n"
                    )
                    await writer.drain()

                elif command.upper() == "STARTTLS":
                    # TLS not implemented yet
                    writer.write(b"454 TLS not available\r\n")
                    await writer.drain()

                elif command.upper().startswith("MAIL FROM:"):
                    raw_from = command[10:].strip()
                    # Extract address before SMTP parameters (e.g., SIZE=...)
                    addr_part = raw_from.split()[0]
                    parsed = parseaddr(addr_part)[1] or addr_part.strip("<> \t\r\n")
                    mail_from = parsed.strip().lower()
                    logger.info(f"🔗 [{connection_id}] Mail from: {mail_from}")
                    writer.write(b"250 OK\r\n")
                    await writer.drain()

                elif command.upper().startswith("RCPT TO:"):
                    # Normalize recipient to pure email address (no display name, no brackets)
                    rcpt_raw = command[8:].strip()
                    rcpt_addr = parseaddr(rcpt_raw)[1] or rcpt_raw.strip("<> \t\r\n")
                    rcpt_addr = rcpt_addr.strip().lower()
                    rcpt_to.append(rcpt_addr)
                    logger.info(
                        f"🔗 [{connection_id}] Rcpt to (normalized): {rcpt_addr} (raw: {rcpt_raw})"
                    )
                    writer.write(b"250 OK\r\n")
                    await writer.drain()

                elif command.upper() == "DATA":
                    data_mode = True
                    logger.info(f"🔗 [{connection_id}] Entering DATA mode")
                    writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                    await writer.drain()

                elif command.upper() == "QUIT":
                    writer.write(b"221 Goodbye\r\n")
                    await writer.drain()
                    break

                else:
                    writer.write(b"500 Command not recognized\r\n")
                    await writer.drain()

        except Exception as e:
            logger.error(f"❌ [{connection_id}] Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"🔗 [{connection_id}] Connection closed")

    async def process_email(
        self, connection_id, peer, mail_from, rcpt_to, data_content
    ):
        """Process incoming email"""
        try:
            logger.info(
                f"🔗 [{connection_id}] Processing email from {mail_from} to {rcpt_to}"
            )

            # Parse the email
            msg = email.message_from_string(data_content)

            # Extract email details
            sender = mail_from or msg.get("From", "").strip()
            # Prefer RCPT command recipients; fallback to parsing To header
            if rcpt_to:
                recipient = rcpt_to[0]
            else:
                recipient = parseaddr(msg.get("To", "") or "")[1].strip().lower()

            # Decode subject (RFC 2047) and strip HTML tags/entities
            raw_subject = msg.get("Subject", "")

            # If no subject or clearly malformed, try robust extraction from raw headers
            def _robust_subject_extract(raw_text: str) -> str:
                # Prefer the first proper 'Subject:' header line (handle folded headers)
                match = re.search(
                    r"^Subject:\s*(.+?)(\r?\n[\t ].+?)*\r?$",
                    raw_text,
                    re.IGNORECASE | re.MULTILINE,
                )
                if not match:
                    return ""
                # Unfold
                unfolded = re.sub(r"\r?\n[\t ]+", " ", match.group(0))
                try:
                    return str(
                        make_header(decode_header(unfolded.split(":", 1)[1].strip()))
                    )
                except Exception:
                    return unfolded.split(":", 1)[1].strip()

            candidate_subject = None
            try:
                if raw_subject:
                    candidate_subject = str(make_header(decode_header(raw_subject)))
            except Exception:
                candidate_subject = raw_subject

            # Filter out known malformed values
            if not candidate_subject or candidate_subject.lower().startswith(
                "message-id:date:"
            ):
                candidate_subject = _robust_subject_extract(data_content)

            decoded_subject = html_unescape.unescape(candidate_subject or "")
            subject = re.sub(r"<[^>]+>", "", decoded_subject).strip()

            # If still no subject, use default
            if not subject:
                subject = "(no subject)"

            logger.info(
                f"📧 [{connection_id}] Email details - From: '{sender}', To: '{recipient}', Subject: '{subject}'"
            )

            # Log email processing
            smtp_logger.log_email_processing(
                "EMAIL_RECEIVED",
                {
                    "connection_id": connection_id,
                    "peer": str(peer),
                    "sender": sender,
                    "recipient": recipient,
                    "subject": subject,
                    "message_size": len(data_content),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Use enhanced MIME parsing for better content extraction
            logger.info(f"🔍 [{connection_id}] Starting enhanced MIME parsing...")
            mime_result = parse_mime_email(data_content)
            html_body = mime_result.get("html") or ""
            plain_body = mime_result.get("plain") or ""
            if html_body and not plain_body:
                plain_body = html_to_text(html_body)
            if plain_body and not html_body:
                html_body = plain_to_html(plain_body)
            body = html_body or plain_body
            # Rewrite cid: links to served attachments endpoint if present
            try:
                attachments = mime_result.get("attachments", [])
                cid_map = {}
                for att in attachments:
                    cid = att.get("content_id")
                    if cid:
                        cid_map[cid] = att
                if cid_map and body:
                    import re as _re

                    def _replace(match):
                        cid = match.group(1)
                        return f"/emails/attachment/cid/{cid}"

                    body = _re.sub(r"cid:([^'\")>\s]+)", _replace, body)
            except Exception:
                pass

            # If body still looks quoted-printable (e.g., =3D, soft breaks), try a final decode
            try:
                if body and ("=3D" in body or "=\n" in body or "=\r\n" in body):
                    import quopri as _quopri

                    decoded_bytes = _quopri.decodestring(body.encode("utf-8", "ignore"))
                    body_decoded = decoded_bytes.decode("utf-8", "ignore")
                    if body_decoded and len(body_decoded) >= len(body) * 0.5:
                        body = body_decoded
            except Exception:
                pass
            # Try base64 fallback when HTML is base64 blob
            try:
                if body and len(body) > 200 and "<" not in body[:200]:
                    import base64 as _b64

                    decoded_bytes = _b64.b64decode(
                        body.encode("utf-8", "ignore"), validate=False
                    )
                    decoded_text = decoded_bytes.decode("utf-8", "ignore")
                    if (
                        "<html" in decoded_text.lower()
                        or "<body" in decoded_text.lower()
                    ):
                        body = decoded_text
            except Exception:
                pass
            # If Hebrew characters exist, wrap with RTL for readability
            try:
                import re as _rtlre

                if body and _rtlre.search(r"[\u0590-\u05FF]", body):
                    if 'dir="rtl"' not in body and "direction:rtl" not in body:
                        body = (
                            "<div dir='rtl' style='direction:rtl;text-align:right'>"
                            + body
                            + "</div>"
                        )
            except Exception:
                pass
            logger.info(
                f"🔍 [{connection_id}] MIME parsing result: content length = {len(body)}"
            )

            # Log attachment information if any
            attachments = mime_result.get("attachments", [])
            if attachments:
                logger.info(
                    f"📎 [{connection_id}] Email has {len(attachments)} attachments:"
                )
                for att in attachments:
                    logger.info(
                        f"📎 [{connection_id}] - {att['filename']} ({att['content_type']}, {att['size']} bytes)"
                    )

            # If no content found, fallback to basic extraction
            if not body or len(body.strip()) < 5:
                logger.warning(
                    f"⚠️ [{connection_id}] No content from MIME parsing, trying fallback..."
                )

                def extract_text_body(message: Message) -> str:
                    if message.is_multipart():
                        # First pass: text/plain
                        for part in message.walk():
                            if part.get_content_type() == "text/plain":
                                return (
                                    decode_payload(
                                        part.get_payload(decode=True),
                                        part.get_content_charset(),
                                    )
                                    or ""
                                )
                        # Second pass: text/html → text
                        for part in message.walk():
                            if part.get_content_type() == "text/html":
                                html_str = (
                                    decode_payload(
                                        part.get_payload(decode=True),
                                        part.get_content_charset(),
                                    )
                                    or ""
                                )
                                return html_to_text(html_str)
                        return ""
                    else:
                        ctype = message.get_content_type()
                        payload = message.get_payload(decode=True)
                        if ctype == "text/plain":
                            return (
                                decode_payload(payload, message.get_content_charset())
                                or ""
                            )
                        if ctype == "text/html":
                            html_str = (
                                decode_payload(payload, message.get_content_charset())
                                or ""
                            )
                            return html_to_text(html_str)
                        return ""

                body = extract_text_body(msg)
                plain_body = body or plain_body
                if plain_body and not html_body:
                    html_body = plain_to_html(plain_body)

            # Normalize recipient to bare address and lowercase
            normalized_recipient = (
                (parseaddr(recipient)[1] or recipient).strip().lower()
            )
            # Normalize sender as well
            normalized_sender = (parseaddr(sender)[1] or sender).strip().lower()
            # Find recipient user (case-insensitive, by email only)
            recipient_user = (
                self.db.query(User)
                .filter(func.lower(User.email) == normalized_recipient)
                .first()
            )

            if recipient_user:
                # Create email record
                # Ensure subject not empty
                safe_subject = subject if subject else "(no subject)"
                if not plain_body and body:
                    lowered = body.lower()
                    if any(tag in lowered for tag in ("<html", "<body", "<div", "<p", "<table", "<br")):
                        plain_body = html_to_text(body)
                        html_body = body
                    else:
                        plain_body = body
                if not html_body and plain_body:
                    html_body = plain_to_html(plain_body)
                if not plain_body:
                    plain_body = body or ""
                mime_type = mime_result.get("mime_type") or "multipart/alternative"
                raw_source = mime_result.get("raw_source") or data_content
                email_record = Email(
                    subject=safe_subject,
                    body=plain_body or body,
                    body_html=html_body,
                    mime_content=raw_source,
                    mime_content_type=mime_type,
                    sender_id=None,  # External sender
                    recipient_id=recipient_user.id,
                    is_external=True,
                    external_sender=normalized_sender,
                )
                self.db.add(email_record)
                self.db.commit()
                self.db.refresh(email_record)

                # CRITICAL: Trigger ActiveSync push notification immediately
                # This notifies any connected iPhone/device via Ping command
                try:
                    from .push_notifications import notify_new_email
                    import asyncio
                    
                    # Notify ActiveSync devices about new email
                    asyncio.create_task(notify_new_email(recipient_user.id, folder_id="1"))
                    
                    logger.info(
                        f"📱 Triggered ActiveSync push notification for user {recipient_user.id}"
                    )
                except Exception as notify_error:
                    # Don't fail email delivery if notification fails
                    logger.warning(
                        f"Failed to trigger ActiveSync notification: {notify_error}"
                    )

                # Send WebSocket notification to recipient
                from .email_parser import get_email_preview
                from .websocket_manager import manager

                # Create email data for notification
                email_data = {
                    "id": email_record.id,
                    "subject": email_record.subject,
                    "sender": sender,
                    "preview": get_email_preview((email_record.body_html or email_record.body or ""), 100),
                    "is_read": email_record.is_read,
                    "created_at": email_record.created_at.isoformat(),
                }

                # Send notification asynchronously
                import asyncio

                asyncio.create_task(
                    manager.send_email_notification(recipient_user.id, email_data)
                )

                # Log successful processing
                smtp_logger.log_internal_email_received(
                    sender, normalized_recipient, subject, len(data_content)
                )
                smtp_logger.log_email_processing(
                    "EMAIL_STORED",
                    {
                        "connection_id": connection_id,
                        "email_id": email_record.id,
                        "sender": sender,
                        "recipient": normalized_recipient,
                        "is_external_sender": True,
                        "recipient_user_id": recipient_user.id,
                    },
                )

                logger.info(
                    f"✅ [{connection_id}] Email received from {sender} to {normalized_recipient} (external: True)"
                )
                logger.info(
                    f"📧 WebSocket notification sent to user {recipient_user.id}"
                )
                return "250 OK"
            else:
                smtp_logger.log_error(
                    "RECIPIENT_NOT_FOUND",
                    f"Recipient {normalized_recipient} not found in system",
                    {
                        "connection_id": connection_id,
                        "sender": sender,
                        "recipient": normalized_recipient,
                        "subject": subject,
                    },
                )
                logger.warning(
                    f"❌ [{connection_id}] Recipient {normalized_recipient} not found in system. Email rejected."
                )
                return "550 Recipient not found"

        except Exception as e:
            error_details = {
                "connection_id": connection_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "message_size": len(data_content),
                "timestamp": datetime.utcnow().isoformat(),
            }

            smtp_logger.log_error("EMAIL_PROCESSING_ERROR", str(e), error_details)
            logger.error(f"❌ [{connection_id}] Error handling email: {e}")
            logger.error(f"❌ [{connection_id}] Error type: {type(e).__name__}")

            import traceback

            logger.error(f"❌ [{connection_id}] Traceback: {traceback.format_exc()}")

            # Log connection details for debugging
            smtp_logger.log_connection("ERROR", error_details)
            return "550 Internal error"
        finally:
            try:
                self.db.close()
                logger.info(f"🔗 [{connection_id}] Database connection closed")
            except Exception as db_error:
                logger.error(f"❌ [{connection_id}] Error closing database: {db_error}")


class SMTPServer:
    def __init__(self, host="localhost", port=1026, ssl_context=None):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.controller = None

    async def start(self):
        handler = EmailHandler(self.ssl_context)
        self.controller = Controller(handler, hostname=self.host, port=self.port)
        self.controller.start()
        logger.info(f"SMTP server started on {self.host}:{self.port}")

    async def stop(self):
        if self.controller:
            self.controller.stop()
            logger.info("SMTP server stopped")


# Global SMTP server instance with TLS support
ssl_context = create_ssl_context()
smtp_server = SMTPServer(ssl_context=ssl_context)


async def start_smtp_server():
    await smtp_server.start()


async def stop_smtp_server():
    await smtp_server.stop()


# Alternative SMTP server for port 25 (requires root privileges)
class SMTPServer25:
    def __init__(self, host="0.0.0.0", port=25, ssl_context=None):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.server = None
        self.handler = None

    async def start(self):
        try:
            # Create custom SMTP server using asyncio with TLS support
            self.handler = EmailHandler(self.ssl_context)

            # Start server
            self.server = await asyncio.start_server(
                self.handler.handle_client, self.host, self.port
            )

            smtp_logger.log_smtp_server_status(
                "STARTED",
                {
                    "host": self.host,
                    "port": self.port,
                    "handler": "EmailHandler (custom asyncio)",
                },
            )
            logger.info(
                f"SMTP server started on {self.host}:{self.port} using custom asyncio"
            )
        except PermissionError:
            smtp_logger.log_error(
                "PERMISSION_DENIED",
                f"Cannot bind to port {self.port}",
                {"port": self.port, "host": self.host},
            )
            logger.error(
                f"Permission denied: Cannot bind to port {self.port}. Try running with sudo or use port 1025 instead."
            )
        except Exception as e:
            smtp_logger.log_error(
                "SERVER_START_ERROR",
                str(e),
                {"port": self.port, "host": self.host, "error_type": type(e).__name__},
            )
            logger.error(f"Error starting SMTP server on port {self.port}: {e}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("SMTP server stopped")


# Global SMTP server instance for port 25 with TLS support
smtp_server_25 = SMTPServer25(ssl_context=ssl_context)


async def start_smtp_server_25():
    """Start SMTP server on port 25 (requires root privileges)"""
    await smtp_server_25.start()


async def stop_smtp_server_25():
    await smtp_server_25.stop()
