"""
ActiveSync Protocol Implementation

Self-contained ActiveSync module for Exchange ActiveSync protocol support.
Designed to be modular and portable for future Docker containerization.
"""

# Import the main router from router.py
try:
    from .router import router
except ImportError:
    # Fallback for development
    router = None

__all__ = ["router"]
