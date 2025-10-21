import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests


@dataclass
class StreamingSubscription:
    subscription_id: str
    user_id: int
    folder_ids: List[str]
    created_at: float = field(default_factory=lambda: time.time())
    last_watermark: str = "WM_0"
    # Simple asyncio queue for events
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    # Expiry/TTL (seconds) - clients may keep long-lived connections; we'll prune old subs
    ttl_seconds: int = 3600

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class EwsPushHub:
    """Minimal in-memory hub for EWS streaming notifications.

    Not durable; sufficient for local testing and Thunderbird streaming events.
    """

    def __init__(self) -> None:
        self._subs: Dict[str, StreamingSubscription] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the event loop that owns hub state for thread-safe scheduling."""
        self._loop = loop

    async def subscribe(
        self, user_id: int, folder_ids: List[str]
    ) -> StreamingSubscription:
        async with self._lock:
            # Cleanup expired
            for sid in list(self._subs.keys()):
                if self._subs[sid].is_expired():
                    self._subs.pop(sid, None)
            sid = f"SUB_{uuid.uuid4()}"
            sub = StreamingSubscription(
                subscription_id=sid, user_id=user_id, folder_ids=folder_ids
            )
            self._subs[sid] = sub
            return sub

    async def unsubscribe(self, subscription_id: str) -> bool:
        async with self._lock:
            return self._subs.pop(subscription_id, None) is not None

    async def get(self, subscription_id: str) -> Optional[StreamingSubscription]:
        async with self._lock:
            return self._subs.get(subscription_id)

    async def publish_new_mail(
        self, user_id: int, folder_id: str, item_id: int
    ) -> None:
        # Fan out to matching subscriptions
        payload = {
            "event_type": "NewMailEvent",
            "watermark": f"WM_{int(time.time())}",
            "time": time.time(),
            "folder_id": folder_id,
            "item_id": item_id,
        }
        async with self._lock:
            for sub in self._subs.values():
                if sub.user_id == user_id and (
                    not sub.folder_ids or folder_id in sub.folder_ids
                ):
                    try:
                        previous = sub.last_watermark
                        sub.last_watermark = payload["watermark"]
                        payload_for_sub = dict(payload)
                        payload_for_sub["previous_watermark"] = previous
                        sub.queue.put_nowait(payload_for_sub)
                    except asyncio.QueueFull:
                        # Drop oldest by draining one entry, then retry
                        try:
                            _ = sub.queue.get_nowait()
                        except Exception:
                            pass
                        try:
                            payload_for_sub = dict(payload)
                            payload_for_sub["previous_watermark"] = previous
                            sub.queue.put_nowait(payload_for_sub)
                        except Exception:
                            pass

    def schedule_publish_new_mail(
        self, user_id: int, folder_id: str, item_id: int
    ) -> bool:
        """Thread-safe helper to enqueue a notification from non-async contexts."""
        loop = self._loop
        if not loop or not loop.is_running():
            return False
        try:
            asyncio.run_coroutine_threadsafe(
                self.publish_new_mail(
                    user_id=user_id, folder_id=folder_id, item_id=item_id
                ),
                loop,
            )
            return True
        except Exception:
            # Ignore scheduling errors so transactional flow is not interrupted
            return False


logger = logging.getLogger(__name__)


def _post_push_event(endpoint: str, token: Optional[str], payload: dict) -> None:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        requests.post(endpoint, json=payload, timeout=3, headers=headers)
    except Exception as exc:
        logger.debug("EWS push HTTP notify failed: %s", exc)


def trigger_ews_push(user_id: int, folder_id: str, item_id: int) -> None:
    """Notify the EWS hub about new mail, with cross-process fallback."""

    if ews_push_hub.schedule_publish_new_mail(user_id, folder_id, item_id):
        return

    endpoint = os.getenv(
        "EWS_PUSH_ENDPOINT", "http://127.0.0.1:8100/internal/ews/push"
    )
    if not endpoint:
        return

    token = os.getenv("EWS_PUSH_TOKEN")
    payload = {
        "user_id": user_id,
        "folder_id": folder_id,
        "item_id": item_id,
    }

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.run_in_executor(None, _post_push_event, endpoint, token, payload)
    else:
        _post_push_event(endpoint, token, payload)


# Global singleton
ews_push_hub = EwsPushHub()
