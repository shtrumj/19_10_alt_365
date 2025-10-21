#!/usr/bin/env python3
"""
Dedicated ActiveSync service entrypoint.
"""

import uvicorn
from fastapi import FastAPI

from app.database import create_tables, ensure_uuid_columns_and_backfill
from app.routers import activesync


def create_app() -> FastAPI:
    app = FastAPI(
        title="365 Email System - ActiveSync Service",
        description="Exchange ActiveSync endpoints",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup():
        create_tables()
        ensure_uuid_columns_and_backfill()

    app.include_router(activesync.router)
    app.include_router(activesync.root_router)

    @app.get("/")
    async def root():
        return {"service": "activesync", "status": "ok"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "activesync"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "run_activesync:app", host="0.0.0.0", port=8200, reload=False, log_level="info"
    )
