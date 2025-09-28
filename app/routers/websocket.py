"""
WebSocket endpoints for real-time email notifications
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db, User
from ..auth import get_current_user_from_cookie
from ..websocket_manager import manager
from ..email_parser import get_email_preview
import logging

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)

@router.websocket("/email-notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time email notifications"""
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            logger.debug(f"📨 Received WebSocket message from user {user_id}: {data}")
            
            # Echo back for connection testing
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"🔗 WebSocket disconnected for user {user_id}")

@router.get("/test-notification/{user_id}")
async def test_notification(user_id: int):
    """Test endpoint to send a notification to a specific user"""
    test_email = {
        "id": 999,
        "subject": "Test Email Notification",
        "sender": "test@example.com",
        "preview": "This is a test email notification",
        "is_read": False
    }
    
    await manager.send_email_notification(user_id, test_email)
    return {"message": f"Test notification sent to user {user_id}"}

@router.get("/test-broadcast")
async def test_broadcast():
    """Test endpoint to broadcast a message to all connected users"""
    message = {
        "type": "system_message",
        "timestamp": "2025-09-28T15:00:00Z",
        "data": {
            "message": "System maintenance in 5 minutes",
            "level": "info"
        }
    }
    
    await manager.broadcast(message)
    return {"message": "Broadcast sent to all connected users"}

@router.get("/connections")
async def get_connections():
    """Get information about active connections"""
    return {
        "total_connections": len(manager.all_connections),
        "user_connections": {
            str(user_id): len(connections) 
            for user_id, connections in manager.active_connections.items()
        }
    }

@router.get("/test")
async def test_websocket_router():
    """Test endpoint to verify WebSocket router is working"""
    return {"message": "WebSocket router is working!", "status": "ok"}
