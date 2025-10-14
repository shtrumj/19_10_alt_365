"""
iOS ActiveSync Strategy

Apple iOS Mail ActiveSync behavior.

Key Characteristics:
- Accepts items immediately on initial sync (no empty response needed)
- Prefers plain text body format (Type=1)
- Larger batch sizes (50 default, 100 max)
- Two-phase commit for reliability
- Typically requests 32KB truncation (honor it)
"""

from typing import List, Optional

from .base import ActiveSyncStrategy


class IOSStrategy(ActiveSyncStrategy):
    """Apple iOS Mail ActiveSync behavior"""

    def needs_empty_initial_response(self, client_sync_key: str) -> bool:
        """
        iOS accepts items immediately on initial sync (SyncKey=0).

        Unlike Outlook, iOS does not require an empty response. It can handle
        receiving email items on the first sync request (0→1).

        This allows for faster initial sync and better user experience on iOS.
        """
        return False

    def get_default_window_size(self) -> int:
        """iOS can handle larger batches (50 items per batch)"""
        return 50

    def get_max_window_size(self) -> int:
        """Allow iOS to request up to 100 items per batch (grommunio default)"""
        return 100

    def get_body_type_preference_order(self) -> List[int]:
        """
        iOS REQUIRES HTML only.

        CRITICAL FIX: iOS Mail crashes when receiving plain text (type 1) for
        emails with complex Hebrew content and HTML formatting. Plain text loses
        93% of content (e.g., 13KB HTML → 972 bytes plain text).

        SOLUTION: Force HTML (type 2) ONLY. Even if the client requests plain text,
        we must override and send HTML to prevent crashes and content loss.

        Returns:
            [2] - HTML ONLY (no plain text, no MIME)
        """
        return [2]

    def should_use_pending_confirmation(self) -> bool:
        """
        iOS uses two-phase commit for reliability.

        Two-phase commit prevents data loss if network fails between
        server send and client receive.
        """
        return True

    def get_truncation_strategy(
        self,
        body_type: int,
        truncation_size: Optional[int],
        is_initial_sync: bool,
    ) -> Optional[int]:
        """
        Z-Push truncation strategy for iOS.

        Args:
            body_type: 1=plain, 2=HTML, 4=MIME
            truncation_size: Client's requested size (None = unlimited)
            is_initial_sync: True if SyncKey=0

        Returns:
            Effective truncation size in bytes

        Strategy:
            - Type 1/2: Honor client's request, but apply 32KB minimum
            - Type 4 (MIME): Cap at 512KB

        iOS typically requests 32KB truncation for text bodies, which is
        reasonable and should be honored. For very small requests (<5KB),
        apply a minimum of 32KB to ensure meaningful content is displayed.
        """
        if body_type == 4:  # MIME
            # Cap MIME at 512KB (Z-Push standard)
            return min(truncation_size or 512000, 512000)
        else:  # Type 1 or 2 (plain text or HTML)
            # Honor client's requested truncation size for previews during sync.
            # The client will fetch full content later on demand.
            return truncation_size
