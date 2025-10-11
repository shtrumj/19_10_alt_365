import base64
import email
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from sqlalchemy.orm import Session

from .database import Email, User
from .email_delivery import email_delivery
from .email_parser import get_email_preview, html_to_text
from .mime_utils import build_mime_message, plain_to_html
from .models import EmailCreate
from .websocket_manager import manager

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, db: Session):
        self.db = db

    def send_email(self, email_data: EmailCreate, sender_id: int) -> Email:
        """Send an email and store it in the database"""
        try:
            # Get sender user
            sender_user = self.db.query(User).filter(User.id == sender_id).first()
            if not sender_user:
                raise ValueError(f"Sender user {sender_id} not found")

            # Check if recipient is internal
            recipient = (
                self.db.query(User)
                .filter(User.email == email_data.recipient_email)
                .first()
            )

            if recipient:
                # Internal recipient - create email record directly
                body_html = email_data.body_html or ""
                body_plain = email_data.body or ""
                if body_html and not body_plain:
                    body_plain = html_to_text(body_html)
                if body_plain and not body_html:
                    body_html = plain_to_html(body_plain)
                mime_content, mime_type = build_mime_message(
                    email_data.subject,
                    sender_user.email,
                    recipient.email,
                    body_plain,
                    body_html if body_html else None,
                )
                mime_content_b64 = base64.b64encode(
                    mime_content.encode("utf-8", errors="ignore")
                ).decode("ascii")
                email_record = Email(
                    subject=email_data.subject,
                    body=body_plain,
                    body_html=body_html,
                    mime_content=mime_content_b64,
                    mime_content_type=mime_type,
                    sender_id=sender_id,
                    recipient_id=recipient.id,
                )

                self.db.add(email_record)
                self.db.commit()
                self.db.refresh(email_record)

                # Send WebSocket notification to recipient
                self._send_email_notification(recipient.id, email_record)

                logger.info(
                    f"Email sent internally from user {sender_id} to {email_data.recipient_email}"
                )
                return email_record
            else:
                # External recipient - queue for delivery
                logger.info(f"Queuing external email to {email_data.recipient_email}")

                # Queue the email for external delivery
                message_id = email_delivery.queue_email(
                    sender_email=sender_user.email,
                    recipient_email=email_data.recipient_email,
                    subject=email_data.subject,
                    body=email_data.body,
                    headers={"X-Sender-ID": str(sender_id)},
                    priority=5,
                )

                # Create a placeholder email record for tracking
                body_html = email_data.body_html or ""
                body_plain = email_data.body or ""
                if body_html and not body_plain:
                    body_plain = html_to_text(body_html)
                if body_plain and not body_html:
                    body_html = plain_to_html(body_plain)
                mime_content, mime_type = build_mime_message(
                    email_data.subject,
                    sender_user.email,
                    email_data.recipient_email,
                    body_plain,
                    body_html if body_html else None,
                )
                mime_content_b64 = base64.b64encode(
                    mime_content.encode("utf-8", errors="ignore")
                ).decode("ascii")
                email_record = Email(
                    subject=email_data.subject,
                    body=body_plain,
                    body_html=body_html,
                    mime_content=mime_content_b64,
                    mime_content_type=mime_type,
                    sender_id=sender_id,
                    recipient_id=None,  # External recipient
                    is_external=True,
                )

                self.db.add(email_record)
                self.db.commit()
                self.db.refresh(email_record)

                logger.info(f"External email queued with message ID {message_id}")
                return email_record

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error sending email: {e}")
            raise

    def _send_smtp_email(self, email_data: EmailCreate, sender_id: int):
        """Send email via SMTP server"""
        try:
            sender_user = self.db.query(User).filter(User.id == sender_id).first()
            if not sender_user:
                return

            # Create message
            msg = MIMEMultipart()
            msg["From"] = sender_user.email
            msg["To"] = email_data.recipient_email
            msg["Subject"] = email_data.subject

            if email_data.body:
                body_html = email_data.body_html or ""
                body_plain = email_data.body or ""
                if body_html and not body_plain:
                    body_plain = html_to_text(body_html)
                if body_plain and not body_html:
                    body_html = plain_to_html(body_plain)
                if body_html:
                    msg.attach(MIMEText(body_plain or "", "plain", "utf-8"))
                    msg.attach(MIMEText(body_html, "html", "utf-8"))
                else:
                    msg.attach(MIMEText(body_plain or "", "plain", "utf-8"))

            # Send via local SMTP server
            with smtplib.SMTP("localhost", 1025) as server:
                server.send_message(msg)

        except Exception as e:
            logger.warning(f"Could not send via SMTP: {e}")

    def get_user_emails(
        self,
        user_id: int,
        folder: str = "inbox",
        limit: int = 50,
        offset: int = 0,
        start_id: int | None = None,
    ) -> List[Email]:
        """Get emails for a user (inbox, sent, etc.), optionally starting after a given ID.

        start_id: when provided, only emails with id > start_id will be returned.
        """
        query = self.db.query(Email)

        if folder == "inbox":
            query = query.filter(
                Email.recipient_id == user_id, Email.is_deleted == False
            )
        elif folder == "sent":
            query = query.filter(Email.sender_id == user_id, Email.is_deleted == False)
        elif folder == "deleted":
            query = query.filter(
                (Email.sender_id == user_id) | (Email.recipient_id == user_id),
                Email.is_deleted == True,
            )

        if start_id is not None:
            query = query.filter(Email.id > start_id)

        # For deterministic paging when using start_id, sort by id ascending
        return query.order_by(Email.id.asc()).offset(offset).limit(limit).all()

    def mark_as_read(self, email_id: int, user_id: int) -> bool:
        """Mark an email as read"""
        email = (
            self.db.query(Email)
            .filter(Email.id == email_id, Email.recipient_id == user_id)
            .first()
        )

        if email:
            email.is_read = True
            self.db.commit()

            # Send WebSocket notification
            self._send_email_update_notification(
                user_id,
                {"email_id": email_id, "action": "mark_as_read", "is_read": True},
            )

            return True
        return False

    def delete_email(self, email_id: int, user_id: int) -> bool:
        """Delete an email (soft delete)"""
        email = (
            self.db.query(Email)
            .filter(
                Email.id == email_id,
                (Email.sender_id == user_id) | (Email.recipient_id == user_id),
            )
            .first()
        )

        if email:
            email.is_deleted = True
            self.db.commit()
            return True
        return False

    def get_email_by_id(self, email_id: int, user_id: int) -> Optional[Email]:
        """Get a specific email by ID"""
        return (
            self.db.query(Email)
            .filter(
                Email.id == email_id,
                (Email.sender_id == user_id) | (Email.recipient_id == user_id),
            )
            .first()
        )

    def get_emails_by_ids(self, user_id: int, email_ids: List[int]) -> List[Email]:
        """Get multiple emails by their IDs for the given user."""
        if not email_ids:
            return []
        return (
            self.db.query(Email)
            .filter(
                Email.id.in_(email_ids),
                ((Email.sender_id == user_id) | (Email.recipient_id == user_id)),
            )
            .all()
        )

    def _send_email_notification(self, user_id: int, email: Email):
        """Send WebSocket notification for new email"""
        try:
            # Get sender information
            sender_email = "Unknown"
            if email.sender:
                sender_email = email.sender.email
            elif email.external_sender:
                sender_email = email.external_sender

            # Create email data for notification
            preview_source = email.body_html or email.body
            email_data = {
                "id": email.id,
                "subject": email.subject,
                "sender": sender_email,
                "preview": get_email_preview(preview_source or "", 100),
                "is_read": email.is_read,
                "created_at": email.created_at.isoformat(),
            }

            # Send notification asynchronously
            import asyncio

            asyncio.create_task(manager.send_email_notification(user_id, email_data))
            logger.info(
                f"📧 WebSocket notification queued for user {user_id}: {email.subject}"
            )

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def _send_email_update_notification(self, user_id: int, update_data: dict):
        """Send WebSocket notification for email update"""
        try:
            import asyncio

            asyncio.create_task(manager.send_email_update(user_id, update_data))
            logger.info(f"📧 Email update notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending email update notification: {e}")
