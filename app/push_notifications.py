#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Push notification manager for ActiveSync Ping command.

This module provides an event-driven system for notifying connected devices
about new content, similar to Z-Push's approach. When new emails arrive,
all active Ping connections are immediately notified.
"""

import asyncio
from typing import Dict, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PushNotificationManager:
    """
    Manages push notifications for ActiveSync devices.
    
    When a Ping request comes in, it subscribes to notifications for specific
    folders (collections). When new content arrives in those folders, all
    subscribed connections are notified immediately.
    """
    
    def __init__(self):
        # Map of user_id -> set of asyncio.Event objects
        self._subscribers: Dict[int, Set[asyncio.Event]] = {}
        # Map of event -> (user_id, folders) for cleanup
        self._event_info: Dict[asyncio.Event, tuple] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, user_id: int, folders: list) -> asyncio.Event:
        """
        Subscribe to push notifications for a user and folders.
        
        Args:
            user_id: The user ID to monitor
            folders: List of folder/collection IDs to monitor
        
        Returns:
            An asyncio.Event that will be set when new content arrives
        """
        event = asyncio.Event()
        
        async with self._lock:
            if user_id not in self._subscribers:
                self._subscribers[user_id] = set()
            
            self._subscribers[user_id].add(event)
            self._event_info[event] = (user_id, folders)
        
        logger.debug(f"Ping subscribed for user {user_id}, folders {folders}")
        return event
    
    async def unsubscribe(self, event: asyncio.Event):
        """
        Unsubscribe from push notifications.
        
        Args:
            event: The event object returned by subscribe()
        """
        async with self._lock:
            if event in self._event_info:
                user_id, _ = self._event_info[event]
                if user_id in self._subscribers:
                    self._subscribers[user_id].discard(event)
                    if not self._subscribers[user_id]:
                        del self._subscribers[user_id]
                del self._event_info[event]
        
        logger.debug(f"Ping unsubscribed")
    
    async def notify_new_content(self, user_id: int, folder_id: str = "1"):
        """
        Notify all subscribed connections that new content has arrived.
        
        This should be called whenever new emails arrive for a user.
        
        Args:
            user_id: The user ID with new content
            folder_id: The folder/collection ID with new content (default: "1" for inbox)
        """
        async with self._lock:
            if user_id in self._subscribers:
                # Notify all subscribers for this user
                for event in self._subscribers[user_id]:
                    event.set()
                
                count = len(self._subscribers[user_id])
                logger.info(f"Notified {count} Ping connection(s) for user {user_id}, folder {folder_id}")
    
    def get_active_connections_count(self) -> int:
        """Get the total number of active Ping connections."""
        return sum(len(events) for events in self._subscribers.values())
    
    def get_user_connections_count(self, user_id: int) -> int:
        """Get the number of active Ping connections for a specific user."""
        return len(self._subscribers.get(user_id, set()))


# Global singleton instance
push_manager = PushNotificationManager()


async def notify_new_email(user_id: int, folder_id: str = "1"):
    """
    Convenience function to notify about new email arrival.
    
    Args:
        user_id: The user ID who received the email
        folder_id: The folder/collection ID (default: "1" for inbox)
    """
    await push_manager.notify_new_content(user_id, folder_id)






