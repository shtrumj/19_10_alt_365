"""
WebSocket manager for real-time email notifications
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Active connections by user_id
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # All active connections for broadcasting
        self.all_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket, user_id: int = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        # Add to user-specific connections
        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            logger.info(f"🔗 WebSocket connected for user {user_id}")
        
        # Add to all connections
        self.all_connections.add(websocket)
        logger.info(f"🔗 Total active connections: {len(self.all_connections)}")
        
    def disconnect(self, websocket: WebSocket, user_id: int = None):
        """Remove a WebSocket connection"""
        # Remove from user-specific connections
        if user_id and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove from all connections
        if websocket in self.all_connections:
            self.all_connections.remove(websocket)
        
        logger.info(f"🔗 WebSocket disconnected. Total connections: {len(self.all_connections)}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send message to specific user"""
        if user_id in self.active_connections:
            dead_connections = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    dead_connections.append(websocket)
            
            # Clean up dead connections
            for websocket in dead_connections:
                self.disconnect(websocket, user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        dead_connections = []
        for websocket in self.all_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for websocket in dead_connections:
            self.all_connections.remove(websocket)
    
    async def send_email_notification(self, user_id: int, email_data: dict):
        """Send new email notification to specific user"""
        # Keep payload aligned with front-end expectations (id, subject, sender, preview, created_at)
        payload = {
            "id": email_data.get("id"),
            "subject": email_data.get("subject"),
            "sender": email_data.get("sender"),
            "preview": email_data.get("preview", ""),
            "is_read": email_data.get("is_read", False),
            "created_at": email_data.get("created_at"),
        }

        message = {
            "type": "new_email",
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }

        await self.send_personal_message(message, user_id)
        logger.info(
            "📧 Email notification sent to user %s: %s",
            user_id,
            payload.get("subject"),
        )
    
    async def send_email_update(self, user_id: int, email_data: dict):
        """Send email update notification (mark as read, delete, etc.)"""
        message = {
            "type": "email_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": email_data
        }
        
        await self.send_personal_message(message, user_id)
        logger.info(f"📧 Email update sent to user {user_id}")

# Global connection manager instance
manager = ConnectionManager()
