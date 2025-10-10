"""
Android ActiveSync Strategy

Android Mail/Gmail ActiveSync behavior (fallback strategy).

Key Characteristics:
- Similar to iOS (accepts items immediately)
- Prefers HTML body format (Type=2)
- Standard batch sizes (25 default, 100 max)
- Two-phase commit for reliability
"""

from typing import List, Optional

from .base import ActiveSyncStrategy


class AndroidStrategy(ActiveSyncStrategy):
    """Android Mail ActiveSync behavior (similar to iOS)"""

    def needs_empty_initial_response(self, client_sync_key: str) -> bool:
        """
        Android accepts items immediately on initial sync.

        Similar to iOS, Android does not require an empty response.
        """
        return False

    def get_default_window_size(self) -> int:
        """Standard default for Android (25 items per batch)"""
        return 25

    def get_max_window_size(self) -> int:
        """Z-Push/Grommunio standard maximum (100 items per batch)"""
        return 100

    def get_body_type_preference_order(self) -> List[int]:
        """
        Android prefers HTML for rich rendering.

        Returns:
            [2, 1, 4] - HTML first, then plain text, then MIME
        """
        return [2, 1, 4]

    def should_use_pending_confirmation(self) -> bool:
        """Android uses two-phase commit for reliability"""
        return True

    def get_truncation_strategy(
        self,
        body_type: int,
        truncation_size: Optional[int],
        is_initial_sync: bool,
    ) -> Optional[int]:
        """
        Z-Push truncation strategy for Android.

        Args:
            body_type: 1=plain, 2=HTML, 4=MIME
            truncation_size: Client's requested size (None = unlimited)
            is_initial_sync: True if SyncKey=0

        Returns:
            Effective truncation size in bytes

        Strategy:
            - Type 1/2: Honor client's request
            - Type 4 (MIME): Cap at 512KB
        """
        if body_type == 4:  # MIME
            return min(truncation_size or 512000, 512000)
        else:  # Type 1 or 2
            return truncation_size
