#!/usr/bin/env python3
"""
Test WebSocket with exact same setup as main app but isolated
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
import json
import logging

# Create exact same setup as main app
app = FastAPI(title="Isolated WebSocket Test")

# Create router with same prefix
router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)

@router.websocket("/email-notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """Isolated WebSocket endpoint"""
    try:
        await websocket.accept()
        
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id,
            "message": "Isolated WebSocket connection successful"
        }))
        
        logger.info(f"🔗 Isolated WebSocket connected for user {user_id}")
        
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Isolated Echo: {data}")
            
    except WebSocketDisconnect:
        logger.info(f"🔗 Isolated WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"🔗 Isolated WebSocket error for user {user_id}: {e}")

@router.get("/test")
async def test_endpoint():
    return {"message": "Isolated WebSocket test working", "status": "ok"}

# Include router (same as main app)
app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Isolated WebSocket Test Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
