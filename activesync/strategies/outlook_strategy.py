"""
Outlook ActiveSync Strategy

Microsoft Outlook Desktop ActiveSync behavior aligned with Z-Push/Grommunio standards.

Key Characteristics:
- Requires empty response on initial sync (SyncKey 0→1)
- Prefers MIME body format (Type=4)
- Conservative batch sizes (25 default, 100 max)
- Two-phase commit for reliability
- Honor client truncation requests for Type=1/2, cap Type=4 at 512KB
"""

from typing import List, Optional

from .base import ActiveSyncStrategy


class OutlookStrategy(ActiveSyncStrategy):
    """Microsoft Outlook Desktop ActiveSync behavior (Z-Push/Grommunio compatible)"""

    def needs_empty_initial_response(self, client_sync_key: str) -> bool:
        """
        Outlook REQUIRES empty response on SyncKey=0 (Z-Push standard).

        This is critical for Outlook Desktop compatibility. Outlook expects:
        1. Sync 0→1: Empty response with folder structure
        2. Sync 1→2: First batch of emails
        3. Sync 2→3: Confirm receipt, get next batch

        If Outlook receives items on 0→1, it rejects the response and retries
        indefinitely, causing the "Connected but not downloading" issue.
        """
        return client_sync_key == "0"

    def get_default_window_size(self) -> int:
        """Conservative default for Outlook (3 items per batch for testing)"""
        return 3

    def get_max_window_size(self) -> int:
        """Match grommunio/Z-Push WindowSize cap for Outlook (512 items)."""
        return 512

    def get_body_type_preference_order(self) -> List[int]:
        """
        Windows Outlook renders best with HTML bodies and uses MIME only for
        explicit attachment fetches. Align with grommunio/z-push ordering.

        Returns:
            [2, 1, 4] - HTML first, then plain text, MIME last
        """
        return [2, 1, 4]

    def should_use_pending_confirmation(self) -> bool:
        """
        Outlook Desktop does not acknowledge pending batches.

        grommunio/z-push commit Outlook batches immediately and rely on the
        client to advance the SyncKey on the next request. Keeping the legacy
        behaviour avoids infinite resend loops when Outlook retries with the
        previous key.
        """
        return False

    def get_truncation_strategy(
        self,
        body_type: int,
        truncation_size: Optional[int],
        is_initial_sync: bool,
    ) -> Optional[int]:
        """
        Z-Push truncation strategy for Outlook.

        Args:
            body_type: 1=plain, 2=HTML, 4=MIME
            truncation_size: Client's requested size (None = unlimited)
            is_initial_sync: True if SyncKey=0

        Returns:
            Effective truncation size in bytes

        Strategy:
            - Type 1/2 (plain/HTML): Honor client's request, but apply 32KB minimum
            - Type 4 (MIME): Cap at 512KB to prevent huge transfers

        This matches Z-Push/Grommunio behavior where the client's truncation
        preference is respected for text bodies, but MIME is capped for safety.

        CRITICAL FIX: Apply minimum of 32KB for Type 1/2 to prevent clients
        from requesting absurdly small sizes (e.g., 500 bytes) that make emails
        unreadable.
        """
        if body_type == 4:  # MIME
            # Cap MIME at 512KB (Z-Push standard)
            return min(truncation_size or 512000, 512000)
        else:  # Type 1 or 2 (plain text or HTML)
            # CRITICAL FIX: Apply minimum truncation of 32KB for text bodies
            # Some clients request tiny sizes (500 bytes) which prevents
            # meaningful email content from being displayed
            MIN_TEXT_TRUNCATION = 32768  # 32KB
            if truncation_size is None:
                return None  # Unlimited
            # Honor client's request, but enforce minimum
            return max(truncation_size, MIN_TEXT_TRUNCATION)
