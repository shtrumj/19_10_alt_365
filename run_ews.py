#!/usr/bin/env python3
"""
Dedicated EWS service entrypoint.
"""

import os

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import create_tables, ensure_uuid_columns_and_backfill
from app.ews_push import ews_push_hub
from app.routers import ews


def create_app() -> FastAPI:
    app = FastAPI(
        title="365 Email System - EWS Service",
        description="SOAP endpoints for Exchange Web Services",
        version="1.0.0",
    )

    @app.on_event("startup")
    async def startup():
        import asyncio

        create_tables()
        ensure_uuid_columns_and_backfill()
        try:
            ews_push_hub.set_loop(asyncio.get_running_loop())
        except RuntimeError:
            pass

    app.include_router(ews.router)

    class PushEvent(BaseModel):
        user_id: int
        folder_id: str
        item_id: int

    @app.post("/internal/ews/push", status_code=204)
    async def internal_push(event: PushEvent, request: Request):
        token = os.getenv("EWS_PUSH_TOKEN")
        if token:
            auth = request.headers.get("Authorization") or ""
            if auth != f"Bearer {token}":
                raise HTTPException(status_code=401, detail="Invalid token")

        await ews_push_hub.publish_new_mail(
            user_id=event.user_id,
            folder_id=event.folder_id,
            item_id=event.item_id,
        )
        return Response(status_code=204)

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
