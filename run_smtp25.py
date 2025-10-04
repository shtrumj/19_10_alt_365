#!/usr/bin/env python3
"""
365 Email System - Run with SMTP on port 25
Note: This requires root privileges to bind to port 25
"""
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import (
    create_tables,
    engine,
    ensure_admin_column,
    ensure_uuid_columns_and_backfill,
    set_admin_user,
)
from app.email_queue import Base as QueueBase
from app.queue_processor import queue_processor
from app.routers import (
    auth,
    autodiscover,
    calendar,
    contacts,
    debug,
    deep_debug,
    emails,
    ews,
    mapihttp,
    oab,
    owa,
    queue,
    rpc_proxy,
    shares,
)
from app.routers import websocket as ws_router
from app.routers import (
    websocket_simple,
)
# Import ActiveSync from its own module
from activesync import router as activesync_router
from app.smtp_server import start_smtp_server_25, stop_smtp_server_25


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    ensure_uuid_columns_and_backfill()
    ensure_admin_column()
    # Ensure Yonatan is admin
    set_admin_user(email="yonatan@shtrum.com", username="yonatan")
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
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(contacts.router)
app.include_router(emails.router)
app.include_router(owa.router)
app.include_router(activesync_router)
app.include_router(queue.router)
app.include_router(debug.router)
app.include_router(websocket_simple.router)
# Include WebSocket routes under /ws
app.include_router(ws_router.router)
# Autodiscover
app.include_router(autodiscover.router)
# EWS SOAP endpoint
app.include_router(ews.router)
# MAPI/HTTP stubs
app.include_router(mapihttp.router)
app.include_router(mapihttp.root_router)
app.include_router(oab.router)
app.include_router(rpc_proxy.router)
app.include_router(deep_debug.router)
app.include_router(shares.router, prefix="/shares")

# Root-level Microsoft-Server-ActiveSync aliases for client compatibility
app.add_api_route(
    "/Microsoft-Server-ActiveSync",
    activesync.eas_options,
    methods=["OPTIONS"],
)
app.add_api_route(
    "/Microsoft-Server-ActiveSync",
    activesync.eas_dispatch,
    methods=["POST"],
)

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
            "smtp_server": "0.0.0.0:25",
        },
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
        log_level="info",
    )
