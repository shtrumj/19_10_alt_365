import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from .database import User, Email
from .models import EmailCreate
from .email_delivery import email_delivery
from typing import List, Optional
import logging

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
            recipient = self.db.query(User).filter(User.email == email_data.recipient_email).first()
            
            if recipient:
                # Internal recipient - create email record directly
                email_record = Email(
                    subject=email_data.subject,
                    body=email_data.body,
                    sender_id=sender_id,
                    recipient_id=recipient.id
                )
                
                self.db.add(email_record)
                self.db.commit()
                self.db.refresh(email_record)
                
                logger.info(f"Email sent internally from user {sender_id} to {email_data.recipient_email}")
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
                    headers={'X-Sender-ID': str(sender_id)},
                    priority=5
                )
                
                # Create a placeholder email record for tracking
                email_record = Email(
                    subject=email_data.subject,
                    body=email_data.body,
                    sender_id=sender_id,
                    recipient_id=None,  # External recipient
                    is_external=True
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
            msg['From'] = sender_user.email
            msg['To'] = email_data.recipient_email
            msg['Subject'] = email_data.subject
            
            if email_data.body:
                msg.attach(MIMEText(email_data.body, 'plain'))
            
            # Send via local SMTP server
            with smtplib.SMTP('localhost', 1025) as server:
                server.send_message(msg)
                
        except Exception as e:
            logger.warning(f"Could not send via SMTP: {e}")
    
    def get_user_emails(self, user_id: int, folder: str = "inbox", limit: int = 50, offset: int = 0) -> List[Email]:
        """Get emails for a user (inbox, sent, etc.)"""
        query = self.db.query(Email)
        
        if folder == "inbox":
            query = query.filter(Email.recipient_id == user_id, Email.is_deleted == False)
        elif folder == "sent":
            query = query.filter(Email.sender_id == user_id, Email.is_deleted == False)
        elif folder == "deleted":
            query = query.filter(
                (Email.sender_id == user_id) | (Email.recipient_id == user_id),
                Email.is_deleted == True
            )
        
        return query.order_by(Email.created_at.desc()).offset(offset).limit(limit).all()
    
    def mark_as_read(self, email_id: int, user_id: int) -> bool:
        """Mark an email as read"""
        email = self.db.query(Email).filter(
            Email.id == email_id,
            Email.recipient_id == user_id
        ).first()
        
        if email:
            email.is_read = True
            self.db.commit()
            return True
        return False
    
    def delete_email(self, email_id: int, user_id: int) -> bool:
        """Delete an email (soft delete)"""
        email = self.db.query(Email).filter(
            Email.id == email_id,
            (Email.sender_id == user_id) | (Email.recipient_id == user_id)
        ).first()
        
        if email:
            email.is_deleted = True
            self.db.commit()
            return True
        return False
    
    def get_email_by_id(self, email_id: int, user_id: int) -> Optional[Email]:
        """Get a specific email by ID"""
        return self.db.query(Email).filter(
            Email.id == email_id,
            (Email.sender_id == user_id) | (Email.recipient_id == user_id)
        ).first()
