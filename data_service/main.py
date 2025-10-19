import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import (
    create_tables,
    ensure_uuid_columns_and_backfill,
)
from data_service.config import settings
from data_service.routers import api_router
from data_service.routers.health import router as health_router

logger = logging.getLogger("data_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.info("Initializing data service")
    create_tables()
    ensure_uuid_columns_and_backfill()
    yield
    logger.info("Data service shutdown complete")


app = FastAPI(title="365 Data Service", version="1.0.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(api_router)


@app.get("/")
async def root():
    return {"service": "data", "status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
