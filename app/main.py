from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import asyncio
from .database import create_tables, engine
from .routers import auth, emails, owa, activesync, queue, debug, websocket_simple, ews, mapihttp
from .smtp_server import start_smtp_server, stop_smtp_server
from .queue_processor import queue_processor
from .email_queue import Base as QueueBase
from .logging_config import setup_logging

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
            "smtp_server": "localhost:1025"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "365-email-system"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
