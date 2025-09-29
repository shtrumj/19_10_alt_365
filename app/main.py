from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import asyncio
from .database import create_tables, engine
from .routers import auth, emails, owa, activesync, queue, debug, websocket_simple, ews, mapihttp, nspi, oab
from .smtp_server import start_smtp_server, stop_smtp_server
from .queue_processor import queue_processor
from .email_queue import Base as QueueBase
from .logging_config import setup_logging
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Setup comprehensive logging
    setup_logging()
    
    create_tables()
    # Create queue tables
    QueueBase.metadata.create_all(bind=engine)
    await start_smtp_server()
    await queue_processor.start()
    yield
    # Shutdown
    await queue_processor.stop()
    await stop_smtp_server()

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
app.include_router(debug.router)
app.include_router(websocket_simple.router)
app.include_router(ews.router)
app.include_router(mapihttp.router)
app.include_router(mapihttp.root_router)
app.include_router(nspi.router)
app.include_router(ews.router)
app.include_router(oab.router)

# Import and register OAB router
from .routers import oab
app.include_router(oab.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Endpoints to serve troubleshooting files from the root
@app.get("/outlook_2021_registry_fix.reg", tags=["Downloads"])
async def download_registry_fix():
    """Serves the Outlook 2021 registry fix file."""
    file_path = "outlook_2021_registry_fix.reg"
    return FileResponse(path=file_path, filename=file_path, media_type='application/octet-stream')

@app.get("/outlook_2021_local_autodiscover.xml", tags=["Downloads"])
async def download_local_autodiscover_xml():
    """Serves the local Autodiscover XML file."""
    file_path = "outlook_2021_local_autodiscover.xml"
    return FileResponse(path=file_path, filename=file_path, media_type='application/xml')

@app.get("/OUTLOOK_2021_SETUP_GUIDE.md", tags=["Downloads"])
async def download_setup_guide():
    """Serves the Outlook 2021 setup guide."""
    file_path = "OUTLOOK_2021_SETUP_GUIDE.md"
    return FileResponse(path=file_path, filename=file_path, media_type='text/markdown')


@app.get("/")
async def root():
    return {
        "message": "365 Email System API",
        "version": "1.0.0",
        "endpoints": {
            "api_docs": "/docs",
            "owa": "/owa",
            "activesync": "/activesync",
            "smtp_server": "localhost:1025"
        }
    }

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
