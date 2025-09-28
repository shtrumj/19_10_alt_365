"""
Email Queue Processor
Background task processor for email delivery queue
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from .email_delivery import email_delivery
from .database import SessionLocal

logger = logging.getLogger(__name__)

class QueueProcessor:
    """Background processor for email delivery queue"""
    
    def __init__(self):
        self.running = False
        self.process_interval = 30  # seconds
        self.task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the queue processor"""
        if self.running:
            logger.warning("Queue processor already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._process_loop())
        logger.info("Email queue processor started")
    
    async def stop(self):
        """Stop the queue processor"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Email queue processor stopped")
    
    async def _process_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                # Get database session
                db = SessionLocal()
                try:
                    # Process email queue
                    await email_delivery.process_queue(db)
                finally:
                    db.close()
                
                # Wait before next processing cycle
                await asyncio.sleep(self.process_interval)
                
            except asyncio.CancelledError:
                logger.info("Queue processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(5)  # Short delay before retry
    
    def get_status(self) -> dict:
        """Get processor status"""
        return {
            'running': self.running,
            'process_interval': self.process_interval,
            'delivery_stats': email_delivery.get_delivery_stats()
        }

# Global queue processor instance
queue_processor = QueueProcessor()
