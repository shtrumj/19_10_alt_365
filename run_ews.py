#!/usr/bin/env python3
"""
Dedicated EWS service entrypoint.
"""

import uvicorn
from fastapi import FastAPI

from app.database import create_tables, ensure_uuid_columns_and_backfill
from app.routers import ews


def create_app() -> FastAPI:
    app = FastAPI(
        title="365 Email System - EWS Service",
        description="SOAP endpoints for Exchange Web Services",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup():
        create_tables()
        ensure_uuid_columns_and_backfill()

    app.include_router(ews.router)

    @app.get("/")
    async def root():
        return {"service": "ews", "status": "ok"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "ews"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("run_ews:app", host="0.0.0.0", port=8100, reload=False, log_level="info")
