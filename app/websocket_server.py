"""
Standalone WebSocket server for real-time email notifications
Bypasses main app authentication issues
"""
import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
from typing import Dict, List, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create standalone FastAPI app
app = FastAPI(title="WebSocket Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WebSocketManager:
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
        
        logger.info(f"🔗 WebSocket disconnected for user {user_id}")
        
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        await websocket.send_text(message)
        
    async def send_email_notification(self, user_id: int, email_data: dict):
        """Send a new email notification to a specific user"""
        message = json.dumps({"type": "new_email", "data": email_data})
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                    logger.info(f"📧 Email notification sent to user {user_id}")
                except Exception as e:
                    logger.error(f"❌ Error sending notification to user {user_id}: {e}")
        else:
            logger.warning(f"⚠️ No active connections for user {user_id}")
            
    async def broadcast(self, message: str):
        """Send a message to all active connections"""
        for connection in self.all_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"❌ Error broadcasting message: {e}")

# Global WebSocket manager
manager = WebSocketManager()

@app.websocket("/ws/email-notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time email notifications - NO AUTHENTICATION"""
    logger.info(f"🔗 New WebSocket connection attempt for user {user_id}")
    
    try:
        await manager.connect(websocket, user_id)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id,
            "message": "WebSocket connection established successfully",
            "timestamp": datetime.now().isoformat()
        }))
        
        logger.info(f"✅ WebSocket connection established for user {user_id}")
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            logger.debug(f"📨 Received message from user {user_id}: {data}")
            
            # Echo back for connection testing
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"🔌 WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)

@app.get("/ws/test")
async def test_websocket():
    """Test endpoint to verify WebSocket server is working"""
    return {
        "message": "WebSocket server is working!",
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(manager.all_connections)
    }

@app.get("/ws/connections")
async def get_connections():
    """Get information about active connections"""
    return {
        "total_connections": len(manager.all_connections),
        "user_connections": {
            str(user_id): len(connections) 
            for user_id, connections in manager.active_connections.items()
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ws/test-notification/{user_id}")
async def test_notification(user_id: int):
    """Test endpoint to send a notification to a specific user"""
    test_email = {
        "id": 999,
        "subject": "Test Email Notification",
        "sender": "test@example.com",
        "preview": "This is a test email notification",
        "is_read": False,
        "created_at": datetime.now().isoformat()
    }
    
    await manager.send_email_notification(user_id, test_email)
    return {"message": f"Test notification sent to user {user_id}"}

@app.get("/")
async def root():
    return {
        "message": "WebSocket Server for 365 Email System",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/email-notifications/{user_id}",
            "test": "/ws/test",
            "connections": "/ws/connections",
            "test_notification": "/ws/test-notification/{user_id}"
        }
    }

if __name__ == "__main__":
    logger.info("🚀 Starting standalone WebSocket server...")
    uvicorn.run(app, host="0.0.0.0", port=8005)
