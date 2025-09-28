"""
Email Queue Management API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..queue_processor import queue_processor
from ..email_delivery import email_delivery
from ..email_queue import email_queue
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["email-queue"])

@router.get("/status")
async def get_queue_status():
    """Get email queue status and statistics"""
    try:
        status = queue_processor.get_status()
        return {
            "queue_processor": status,
            "message": "Email queue status retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_queue_stats():
    """Get detailed queue statistics"""
    try:
        stats = email_queue.get_queue_stats()
        return {
            "queue_stats": stats,
            "message": "Queue statistics retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process")
async def process_queue():
    """Manually trigger queue processing"""
    try:
        db = next(get_db())
        await email_delivery.process_queue(db)
        return {
            "message": "Queue processing triggered successfully"
        }
    except Exception as e:
        logger.error(f"Error processing queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_emails(days: int = 30):
    """Clean up old emails from queue"""
    try:
        cleaned_count = email_queue.cleanup_old_emails(days)
        return {
            "cleaned_count": cleaned_count,
            "message": f"Cleaned up {cleaned_count} old emails"
        }
    except Exception as e:
        logger.error(f"Error cleaning up queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def queue_health_check():
    """Health check for email queue system"""
    try:
        status = queue_processor.get_status()
        return {
            "status": "healthy" if status['running'] else "unhealthy",
            "queue_processor": status['running'],
            "delivery_stats": status['delivery_stats']
        }
    except Exception as e:
        logger.error(f"Error in queue health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
