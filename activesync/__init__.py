"""
ActiveSync Protocol Implementation

Self-contained ActiveSync module for Exchange ActiveSync protocol support.
Designed to be modular and portable for future Docker containerization.
"""

# Import the main router from router.py (guarded - do not break on syntax errors during refactor)
try:
    from .router import router
except Exception:
    router = None

__all__ = ["router"]
