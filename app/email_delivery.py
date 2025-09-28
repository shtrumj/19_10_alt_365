"""
Email Delivery Service
Orchestrates email delivery to external recipients
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from .mx_lookup import mx_lookup
from .email_queue import email_queue, QueuedEmail, EmailQueueStatus
from .smtp_client import smtp_client, SMTPDeliveryResult
from .database import get_db, User

logger = logging.getLogger(__name__)

class EmailDeliveryService:
    """Service for delivering emails to external recipients"""
    
    def __init__(self):
        self.email_queue = email_queue
        self.processing = False
        self.batch_size = 10
        self.retry_delays = [1, 5, 15, 60]  # Minutes between retries
    
    async def process_queue(self, db: Session = None):
        """
        Process email queue - main entry point
        
        Args:
            db: Database session
        """
        if self.processing:
            logger.warning("Email delivery service already processing")
            return
        
        self.processing = True
        try:
            logger.info("Starting email queue processing")
            
            # Process pending emails
            await self._process_pending_emails(db)
            
            # Process retry emails
            await self._process_retry_emails(db)
            
            logger.info("Email queue processing completed")
            
        except Exception as e:
            logger.error(f"Error processing email queue: {e}")
        finally:
            self.processing = False
    
    async def _process_pending_emails(self, db: Session = None):
        """Process pending emails from queue"""
        try:
            pending_emails = email_queue.get_pending_emails(self.batch_size)
            logger.info(f"Processing {len(pending_emails)} pending emails")
            
            for email in pending_emails:
                await self._process_single_email(email, db)
                
        except Exception as e:
            logger.error(f"Error processing pending emails: {e}")
    
    async def _process_retry_emails(self, db: Session = None):
        """Process emails ready for retry"""
        try:
            retry_emails = email_queue.get_retry_emails(self.batch_size)
            logger.info(f"Processing {len(retry_emails)} retry emails")
            
            for email in retry_emails:
                await self._process_single_email(email, db)
                
        except Exception as e:
            logger.error(f"Error processing retry emails: {e}")
    
    async def _process_single_email(self, queued_email: QueuedEmail, db: Session = None):
        """
        Process a single queued email
        
        Args:
            queued_email: QueuedEmail object
            db: Database session
        """
        try:
            logger.info(f"Processing email {queued_email.message_id} to {queued_email.recipient_email}")
            
            # Mark as processing
            email_queue.mark_as_processing(queued_email.message_id)
            
            # Check if recipient is internal or external
            if self._is_internal_recipient(queued_email.recipient_email, db):
                await self._deliver_internal_email(queued_email, db)
            else:
                await self._deliver_external_email(queued_email)
                
        except Exception as e:
            logger.error(f"Error processing email {queued_email.message_id}: {e}")
            email_queue.mark_as_failed(queued_email.message_id, str(e))
    
    def _is_internal_recipient(self, email: str, db: Session = None) -> bool:
        """
        Check if recipient is internal user
        
        Args:
            email: Recipient email address
            db: Database session
            
        Returns:
            True if internal user, False if external
        """
        try:
            if not db:
                from .database import SessionLocal
                db = SessionLocal()
            
            user = db.query(User).filter(User.email == email).first()
            is_internal = user is not None
            
            logger.debug(f"Recipient {email} is {'internal' if is_internal else 'external'}")
            return is_internal
            
        except Exception as e:
            logger.error(f"Error checking if recipient is internal: {e}")
            return False
    
    async def _deliver_internal_email(self, queued_email: QueuedEmail, db: Session):
        """
        Deliver email to internal recipient
        
        Args:
            queued_email: QueuedEmail object
            db: Database session
        """
        try:
            from .database import Email, User
            
            # Find recipient user
            recipient_user = db.query(User).filter(
                User.email == queued_email.recipient_email
            ).first()
            
            if not recipient_user:
                error_msg = f"Internal recipient {queued_email.recipient_email} not found"
                logger.error(error_msg)
                email_queue.mark_as_failed(queued_email.message_id, error_msg)
                return
            
            # Find sender user
            sender_user = db.query(User).filter(
                User.email == queued_email.sender_email
            ).first()
            
            if not sender_user:
                error_msg = f"Sender {queued_email.sender_email} not found"
                logger.error(error_msg)
                email_queue.mark_as_failed(queued_email.message_id, error_msg)
                return
            
            # Create email record
            email_record = Email(
                subject=queued_email.subject,
                body=queued_email.body,
                sender_id=sender_user.id,
                recipient_id=recipient_user.id,
                is_read=False
            )
            
            db.add(email_record)
            db.commit()
            
            logger.info(f"Delivered internal email {queued_email.message_id} to {queued_email.recipient_email}")
            email_queue.mark_as_sent(queued_email.message_id)
            
        except Exception as e:
            logger.error(f"Error delivering internal email: {e}")
            email_queue.mark_as_failed(queued_email.message_id, str(e))
    
    async def _deliver_external_email(self, queued_email: QueuedEmail):
        """
        Deliver email to external recipient
        
        Args:
            queued_email: QueuedEmail object
        """
        try:
            logger.info(f"Delivering external email to {queued_email.recipient_email}")
            
            # Get delivery information (MX records, etc.)
            delivery_info = mx_lookup.get_delivery_info(queued_email.recipient_email)
            
            if not delivery_info:
                error_msg = f"Could not get delivery info for {queued_email.recipient_email}"
                logger.error(error_msg)
                email_queue.mark_as_failed(queued_email.message_id, error_msg)
                return
            
            # Update queue with delivery info
            email_queue.update_status(
                queued_email.message_id,
                EmailQueueStatus.PROCESSING,
                delivery_info=delivery_info
            )
            
            # Attempt delivery
            result = smtp_client.deliver_email(
                sender=queued_email.sender_email,
                recipient=queued_email.recipient_email,
                subject=queued_email.subject,
                body=queued_email.body,
                headers=queued_email.headers or {},
                mx_server=delivery_info['best_mx_server'],
                mx_port=delivery_info['port']
            )
            
            if result.success:
                logger.info(f"Successfully delivered email {queued_email.message_id} to {queued_email.recipient_email}")
                email_queue.mark_as_sent(queued_email.message_id)
            else:
                error_msg = f"Delivery failed: {result.error_message}"
                logger.error(f"Failed to deliver email {queued_email.message_id}: {error_msg}")
                
                # Check if we should retry
                if queued_email.retry_count < queued_email.max_retries:
                    email_queue.mark_for_retry(queued_email.message_id, error_msg)
                else:
                    email_queue.mark_as_failed(queued_email.message_id, error_msg)
            
        except Exception as e:
            logger.error(f"Error delivering external email: {e}")
            email_queue.mark_as_failed(queued_email.message_id, str(e))
    
    def queue_email(self,
                   sender_email: str,
                   recipient_email: str,
                   subject: str,
                   body: str,
                   headers: Dict = None,
                   priority: int = 5) -> str:
        """
        Queue email for delivery
        
        Args:
            sender_email: Sender email address
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body
            headers: Additional headers
            priority: Queue priority (1-10)
            
        Returns:
            Message ID
        """
        try:
            # Generate unique message ID
            message_id = f"{uuid.uuid4()}@365-email.local"
            
            # Add to queue
            queued_email = email_queue.add_email(
                message_id=message_id,
                sender_email=sender_email,
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                headers=headers,
                priority=priority
            )
            
            logger.info(f"Queued email {message_id} for delivery to {recipient_email}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error queuing email: {e}")
            raise
    
    def get_delivery_stats(self) -> Dict:
        """
        Get delivery statistics
        
        Returns:
            Dictionary with delivery statistics
        """
        try:
            stats = email_queue.get_queue_stats()
            stats['processing'] = self.processing
            return stats
        except Exception as e:
            logger.error(f"Error getting delivery stats: {e}")
            return {}

# Global delivery service instance
email_delivery = EmailDeliveryService()
