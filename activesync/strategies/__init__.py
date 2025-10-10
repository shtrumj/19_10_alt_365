"""
ActiveSync Strategy Pattern

Separates client-specific behavior (Outlook, iOS, Android) into dedicated strategy classes.
This ensures clean separation of concerns and makes it easy to add new client types.
"""

from .base import ActiveSyncStrategy
from .factory import get_activesync_strategy
from .ios_strategy import IOSStrategy
from .outlook_strategy import OutlookStrategy

__all__ = [
    "get_activesync_strategy",
    "ActiveSyncStrategy",
    "OutlookStrategy",
    "IOSStrategy",
]
