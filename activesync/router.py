"""Legacy compatibility wrapper for ActiveSync router.

All application logic lives in ``app.routers.activesync``.  This module simply
re-exports the FastAPI router and the alias handlers so existing imports keep
working (for example, ``app.main`` still imports from ``activesync.router``).
"""

from app.routers.activesync import router, eas_options, eas_dispatch

__all__ = ["router", "eas_options", "eas_dispatch"]
