"""
Email Queue System
Handles queuing and processing of outbound emails
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from .database import SessionLocal

logger = logging.getLogger(__name__)

# Email queue database model
Base = declarative_base()

class EmailQueueStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"

class QueuedEmail(Base):
    __tablename__ = "queued_emails"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    sender_email = Column(String, index=True)
    recipient_email = Column(String, index=True)
    subject = Column(String)
    body = Column(Text)
    headers = Column(JSON)  # Store email headers as JSON
    status = Column(String, default=EmailQueueStatus.PENDING.value)
    priority = Column(Integer, default=5)  # 1=highest, 10=lowest
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    sent_at = Column(DateTime)
    error_message = Column(Text)
    delivery_info = Column(JSON)  # Store MX/delivery information

class EmailQueue:
    """Email queue management system"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.processing = False
    
    def add_email(self, 
                  message_id: str,
                  sender_email: str,
                  recipient_email: str,
                  subject: str,
                  body: str,
                  headers: Dict = None,
                  priority: int = 5) -> QueuedEmail:
        """
        Add email to queue
        
        Args:
            message_id: Unique message identifier
            sender_email: Sender email address
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body
            headers: Email headers dictionary
            priority: Queue priority (1-10, lower = higher priority)
            
        Returns:
            QueuedEmail object
        """
        try:
            # Check if email already exists
            existing = self.db.query(QueuedEmail).filter(
                QueuedEmail.message_id == message_id
            ).first()
            
            if existing:
                logger.warning(f"Email {message_id} already in queue")
                return existing
            
            # Create new queued email
            now = datetime.utcnow()
            queued_email = QueuedEmail(
                message_id=message_id,
                sender_email=sender_email,
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                headers=headers or {},
                priority=priority,
                status=EmailQueueStatus.PENDING.value,
                created_at=now,
                updated_at=now
            )
            
            self.db.add(queued_email)
            self.db.commit()
            self.db.refresh(queued_email)
            
            logger.info(f"Added email {message_id} to queue (priority: {priority})")
            return queued_email
            
        except Exception as e:
            logger.error(f"Error adding email to queue: {e}")
            self.db.rollback()
            raise
    
    def get_pending_emails(self, limit: int = 10) -> List[QueuedEmail]:
        """
        Get pending emails from queue, ordered by priority and creation time
        
        Args:
            limit: Maximum number of emails to return
            
        Returns:
            List of QueuedEmail objects
        """
        try:
            emails = self.db.query(QueuedEmail).filter(
                QueuedEmail.status == EmailQueueStatus.PENDING.value
            ).order_by(
                QueuedEmail.priority.asc(),
                QueuedEmail.created_at.asc()
            ).limit(limit).all()
            
            logger.info(f"Retrieved {len(emails)} pending emails from queue")
            return emails
            
        except Exception as e:
            logger.error(f"Error retrieving pending emails: {e}")
            return []
    
    def get_retry_emails(self, limit: int = 10) -> List[QueuedEmail]:
        """
        Get emails ready for retry
        
        Args:
            limit: Maximum number of emails to return
            
        Returns:
            List of QueuedEmail objects ready for retry
        """
        try:
            now = datetime.utcnow()
            emails = self.db.query(QueuedEmail).filter(
                QueuedEmail.status == EmailQueueStatus.RETRY.value,
                QueuedEmail.next_retry_at <= now,
                QueuedEmail.retry_count < QueuedEmail.max_retries
            ).order_by(
                QueuedEmail.priority.asc(),
                QueuedEmail.next_retry_at.asc()
            ).limit(limit).all()
            
            logger.info(f"Retrieved {len(emails)} emails ready for retry")
            return emails
            
        except Exception as e:
            logger.error(f"Error retrieving retry emails: {e}")
            return []
    
    def update_status(self, 
                     message_id: str, 
                     status: EmailQueueStatus,
                     error_message: str = None,
                     delivery_info: Dict = None) -> bool:
        """
        Update email status in queue
        
        Args:
            message_id: Email message ID
            status: New status
            error_message: Error message if failed
            delivery_info: Delivery information
            
        Returns:
            True if updated successfully
        """
        try:
            email = self.db.query(QueuedEmail).filter(
                QueuedEmail.message_id == message_id
            ).first()
            
            if not email:
                logger.error(f"Email {message_id} not found in queue")
                return False
            
            email.status = status.value
            email.updated_at = datetime.utcnow()
            
            if error_message:
                email.error_message = error_message
            
            if delivery_info:
                email.delivery_info = delivery_info
            
            if status == EmailQueueStatus.SENT:
                email.sent_at = datetime.utcnow()
            elif status == EmailQueueStatus.RETRY:
                email.retry_count += 1
                # Exponential backoff: 2^retry_count minutes
                retry_delay = 2 ** email.retry_count
                email.next_retry_at = datetime.utcnow() + timedelta(minutes=retry_delay)
            
            self.db.commit()
            logger.info(f"Updated email {message_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating email status: {e}")
            self.db.rollback()
            return False
    
    def mark_as_processing(self, message_id: str) -> bool:
        """Mark email as being processed"""
        return self.update_status(message_id, EmailQueueStatus.PROCESSING)
    
    def mark_as_sent(self, message_id: str) -> bool:
        """Mark email as sent successfully"""
        return self.update_status(message_id, EmailQueueStatus.SENT)
    
    def mark_as_failed(self, message_id: str, error_message: str) -> bool:
        """Mark email as failed"""
        return self.update_status(message_id, EmailQueueStatus.FAILED, error_message)
    
    def mark_for_retry(self, message_id: str, error_message: str) -> bool:
        """Mark email for retry"""
        return self.update_status(message_id, EmailQueueStatus.RETRY, error_message)
    
    def get_queue_stats(self) -> Dict:
        """
        Get queue statistics
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            stats = {}
            for status in EmailQueueStatus:
                count = self.db.query(QueuedEmail).filter(
                    QueuedEmail.status == status.value
                ).count()
                stats[status.value] = count
            
            # Add retry information
            retry_ready = self.db.query(QueuedEmail).filter(
                QueuedEmail.status == EmailQueueStatus.RETRY.value,
                QueuedEmail.next_retry_at <= datetime.utcnow()
            ).count()
            stats['retry_ready'] = retry_ready
            
            logger.info(f"Queue stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def cleanup_old_emails(self, days: int = 30) -> int:
        """
        Clean up old sent/failed emails
        
        Args:
            days: Number of days to keep emails
            
        Returns:
            Number of emails cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old sent emails
            sent_count = self.db.query(QueuedEmail).filter(
                QueuedEmail.status == EmailQueueStatus.SENT.value,
                QueuedEmail.sent_at < cutoff_date
            ).delete()
            
            # Delete old failed emails
            failed_count = self.db.query(QueuedEmail).filter(
                QueuedEmail.status == EmailQueueStatus.FAILED.value,
                QueuedEmail.updated_at < cutoff_date
            ).delete()
            
            self.db.commit()
            total_cleaned = sent_count + failed_count
            
            logger.info(f"Cleaned up {total_cleaned} old emails (sent: {sent_count}, failed: {failed_count})")
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning up old emails: {e}")
            self.db.rollback()
            return 0

# Global queue instance
email_queue = EmailQueue()
