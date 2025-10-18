import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
                        sub.last_watermark = payload["watermark"]
                        sub.queue.put_nowait(payload)
                    except asyncio.QueueFull:
                        # Drop oldest by draining one
                        try:
                            _ = sub.queue.get_nowait()
                        except Exception:
                            pass
                        try:
                            sub.queue.put_nowait(payload)
                        except Exception:
                            pass


# Global singleton
ews_push_hub = EwsPushHub()
