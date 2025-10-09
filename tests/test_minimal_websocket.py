#!/usr/bin/env python3
"""
Minimal WebSocket test to debug the 403 Forbidden issue
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import json

app = FastAPI(title="Minimal WebSocket Test")

@app.websocket("/test-ws")
async def websocket_endpoint(websocket: WebSocket):
    """Minimal WebSocket endpoint"""
    try:
        await websocket.accept()
        print("✅ WebSocket connection accepted")
        
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "Minimal WebSocket connection successful"
        }))
        
        while True:
            data = await websocket.receive_text()
            print(f"📨 Received: {data}")
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        print("🔗 WebSocket disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

@app.get("/")
async def root():
    return {"message": "Minimal WebSocket test server"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
