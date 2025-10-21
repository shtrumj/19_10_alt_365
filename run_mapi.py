#!/usr/bin/env python3
"""
Dedicated MAPI/HTTP service entrypoint.
Serves the /mapi endpoints separately from the OWA/UI service.
"""

import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI

from sqlalchemy.exc import SQLAlchemyError

from app.database import set_admin_user
from app.routers import mapihttp

logger = logging.getLogger("run_mapi")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        set_admin_user(email="yonatan@shtrum.com", username="yonatan")
    except SQLAlchemyError as exc:
        logger.warning("Skipping admin user setup during MAPI startup: %s", exc)
    except Exception as exc:  # noqa: BLE001 - surface unexpected issues
        logger.warning("Unexpected error during MAPI startup init: %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="365 Email System - MAPI Service",
        description="Standalone MAPI/HTTP endpoints for Outlook clients",
        version="1.0.0",
        lifespan=_lifespan,
    )

    app.include_router(mapihttp.router)
    app.include_router(mapihttp.root_router)

    @app.get("/")
    async def root():
        return {"service": "mapi", "status": "ok"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "mapi"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "run_mapi:app",
        host="0.0.0.0",
        port=8300,
        reload=False,
        log_level="info",
    )
