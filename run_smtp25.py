#!/usr/bin/env python3
"""
365 Email System - Run with SMTP on port 25
Note: This requires root privileges to bind to port 25
"""
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from app.database import create_tables, engine
from app.routers import auth, emails, owa, activesync, queue
from app.smtp_server import start_smtp_server_25, stop_smtp_server_25
from app.queue_processor import queue_processor
from app.email_queue import Base as QueueBase
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    # Create queue tables
    QueueBase.metadata.create_all(bind=engine)
    await start_smtp_server_25()  # Use port 25 SMTP server
    await queue_processor.start()
    yield
    # Shutdown
    await queue_processor.stop()
    await stop_smtp_server_25()  # Stop port 25 SMTP server

# Create app with custom lifespan
app = FastAPI(
    title="365 Email System",
    description="A Microsoft 365-like email system with FastAPI, SQLite, and ActiveSync support",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(owa.router)
app.include_router(activesync.router)
app.include_router(queue.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return {
        "message": "365 Email System API",
        "version": "1.0.0",
        "endpoints": {
            "api_docs": "/docs",
            "owa": "/owa",
            "activesync": "/activesync",
            "smtp_server": "0.0.0.0:25"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "365-email-system"}

if __name__ == "__main__":
    print("Starting 365 Email System with SMTP on port 25...")
    print("Note: This requires root privileges to bind to port 25")
    print("SMTP Server: 0.0.0.0:25 (all interfaces)")
    print("Web Interface: http://localhost:8001/owa")
    print("API Documentation: http://localhost:8001/docs")
    print("ActiveSync: http://localhost:8001/activesync")
    
    uvicorn.run(
        "run_smtp25:app",
        host="0.0.0.0",
        port=8001,
        reload=False,  # Disable reload for production
        log_level="info"
    )
