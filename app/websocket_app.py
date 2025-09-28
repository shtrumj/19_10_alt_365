"""
Isolated WebSocket FastAPI app with no authentication
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .websocket_manager import manager
import logging
import json

# Create a separate FastAPI app for WebSocket connections
websocket_app = FastAPI(title="WebSocket Server", version="1.0.0")
logger = logging.getLogger(__name__)

@websocket_app.websocket("/ws/email-notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time email notifications - NO AUTHENTICATION"""
    try:
        await websocket.accept()
        await manager.connect(websocket, user_id)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id,
            "message": "WebSocket connection established successfully"
        }))
        
        logger.info(f"🔗 WebSocket connected for user {user_id}")
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            logger.debug(f"📨 Received WebSocket message from user {user_id}: {data}")
            
            # Echo back for connection testing
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"🔗 WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"🔗 WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)

@websocket_app.get("/ws/test")
async def test_websocket():
    """Test endpoint to verify WebSocket app is working"""
    return {"message": "WebSocket app is working!", "status": "ok"}

@websocket_app.get("/ws/connections")
async def get_connections():
    """Get information about active connections"""
    return {
        "total_connections": len(manager.all_connections),
        "user_connections": {
            str(user_id): len(connections) 
            for user_id, connections in manager.active_connections.items()
        }
    }
