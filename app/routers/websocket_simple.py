"""
Simple WebSocket endpoints for real-time email notifications
No authentication dependencies
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..websocket_manager import manager

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/email-notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time email notifications - NO AUTHENTICATION"""
    try:
        await manager.connect(websocket, user_id)

        # Send connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_established",
                    "user_id": user_id,
                    "message": "WebSocket connection established successfully",
                }
            )
        )

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


@router.get("/test")
async def test_websocket_router():
    """Test endpoint to verify WebSocket router is working"""
    return {"message": "WebSocket router is working!", "status": "ok"}


@router.get("/connections")
async def get_connections():
    """Get information about active connections"""
    return {
        "total_connections": len(manager.all_connections),
        "user_connections": {
            str(user_id): len(connections)
            for user_id, connections in manager.active_connections.items()
        },
    }
