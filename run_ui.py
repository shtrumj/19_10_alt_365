#!/usr/bin/env python3
"""
UI service entrypoint for the 365 Email System.
Includes OWA, REST APIs, queue processor, and SMTP listener.
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
    caldav_carddav,
    calendar,
    contacts,
    debug,
    deep_debug,
    emails,
    ews,
    oab,
    owa,
    queue,
    rpc_proxy,
    shares,
)
from app.routers import websocket as ws_router
from app.routers import websocket_simple
from app.smtp_server import start_smtp_server_25, stop_smtp_server_25


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database preparation
    create_tables()
    ensure_uuid_columns_and_backfill()
    ensure_admin_column()
    set_admin_user(email="yonatan@shtrum.com", username="yonatan")
    QueueBase.metadata.create_all(bind=engine)

    # Start background services (SMTP + queue processor)
    await start_smtp_server_25()
    await queue_processor.start()
    try:
        yield
    finally:
        await queue_processor.stop()
        await stop_smtp_server_25()


app = FastAPI(
    title="365 Email System UI",
    description="OWA and management endpoints",
    version="1.0.0",
    lifespan=lifespan,
)

# UI/API routers
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(contacts.router)
app.include_router(emails.router)
app.include_router(owa.router)
app.include_router(queue.router)
app.include_router(debug.router)
app.include_router(websocket_simple.router)
app.include_router(ws_router.router)
app.include_router(autodiscover.router)
app.include_router(ews.router)
app.include_router(caldav_carddav.router)
app.include_router(oab.router)
app.include_router(rpc_proxy.router)
app.include_router(deep_debug.router)
app.include_router(shares.router, prefix="/shares")

# Static assets
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {
        "message": "365 Email System UI service",
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
    return {"status": "healthy", "service": "ui"}


if __name__ == "__main__":
    uvicorn.run(
        "run_ui:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )
