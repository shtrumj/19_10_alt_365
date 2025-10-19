from fastapi import APIRouter

from . import emails, health, users

api_router = APIRouter(prefix="/internal", tags=["internal"])

api_router.include_router(users.router)
api_router.include_router(emails.router)

__all__ = ["api_router"]
