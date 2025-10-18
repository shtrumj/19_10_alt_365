import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import ActiveSync from the new top-level module
from activesync.router import router as activesync_router
from app.routers.activesync import eas_dispatch as eas_dispatch_handler
from app.routers.activesync import eas_options as eas_options_handler

from .config import settings
from .database import create_tables, engine, ensure_uuid_columns_and_backfill
from .email_queue import Base as QueueBase
from .logging_config import setup_logging
from .queue_processor import queue_processor
from .routers import (
    auth,
    calendar,
    caldav_carddav,
    contacts,
    debug,
    deep_debug,
    emails,
    ews,
    mapihttp,
    modern_auth,
    oab,
    owa,
    queue,
    rpc_proxy,
    shares,
    websocket_simple,
)
from .smtp_server import start_smtp_server, stop_smtp_server

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Setup comprehensive logging
    setup_logging()

    create_tables()
    ensure_uuid_columns_and_backfill()
    # Create queue tables
    QueueBase.metadata.create_all(bind=engine)
    logger.info("Starting SMTP server and queue processor")
    await start_smtp_server()
    await queue_processor.start()
    yield
    # Shutdown
    logger.info("Shutting down SMTP server and queue processor")
    await queue_processor.stop()
    await stop_smtp_server()


app = FastAPI(
    title="365 Email System",
    description="A Microsoft 365-like email system with FastAPI, SQLite, and ActiveSync support",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router)
app.include_router(modern_auth.router)
app.include_router(emails.router)
app.include_router(owa.router)
app.include_router(calendar.router)
app.include_router(contacts.router)
app.include_router(activesync_router)
app.include_router(queue.router)
app.include_router(debug.router)
app.include_router(websocket_simple.router)
app.include_router(ews.router)
app.include_router(caldav_carddav.router)
app.include_router(mapihttp.router)
app.include_router(mapihttp.root_router)
app.include_router(oab.router)
app.include_router(rpc_proxy.router)
app.include_router(deep_debug.router)
app.include_router(shares.router, prefix="/shares")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root-level Microsoft-Server-ActiveSync aliases for client compatibility
app.add_api_route(
    "/Microsoft-Server-ActiveSync",
    eas_options_handler,
    methods=["OPTIONS"],
)
app.add_api_route(
    "/Microsoft-Server-ActiveSync",
    eas_dispatch_handler,
    methods=["POST"],
)


# Endpoints to serve troubleshooting files from the root
@app.get("/outlook_2021_registry_fix.reg", tags=["Downloads"])
async def download_registry_fix():
    """Serves the Outlook 2021 registry fix file."""
    file_path = "outlook_2021_registry_fix.reg"
    return FileResponse(
        path=file_path, filename=file_path, media_type="application/octet-stream"
    )


@app.get("/outlook_2021_local_autodiscover.xml", tags=["Downloads"])
async def download_local_autodiscover_xml():
    """Serves the local Autodiscover XML file."""
    file_path = "outlook_2021_local_autodiscover.xml"
    return FileResponse(
        path=file_path, filename=file_path, media_type="application/xml"
    )


@app.get("/OUTLOOK_2021_SETUP_GUIDE.md", tags=["Downloads"])
async def download_setup_guide():
    """Serves the Outlook 2021 setup guide."""
    file_path = "OUTLOOK_2021_SETUP_GUIDE.md"
    return FileResponse(path=file_path, filename=file_path, media_type="text/markdown")


@app.get("/")
async def root():
    return {
        "message": "365 Email System API",
        "version": "1.0.0",
        "endpoints": {
            "api_docs": "/docs",
            "owa": "/owa",
            "activesync": "/activesync",
            "smtp_server": "localhost:1025",
        },
    }


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
