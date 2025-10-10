"""
Base ActiveSync Strategy

Abstract base class defining the interface for client-specific ActiveSync behavior.
All concrete strategy classes (Outlook, iOS, Android) must implement these methods.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class ActiveSyncStrategy(ABC):
    """Base class for client-specific ActiveSync behavior"""

    @abstractmethod
    def needs_empty_initial_response(self, client_sync_key: str) -> bool:
        """
        Whether client expects empty response on initial sync (0→1).

        Args:
            client_sync_key: The sync key sent by the client

        Returns:
            True if client expects empty response on SyncKey=0, False otherwise

        Example:
            Outlook: True (Z-Push standard - empty response on 0→1)
            iOS: False (accepts items immediately)
        """
        pass

    @abstractmethod
    def get_default_window_size(self) -> int:
        """
        Default batch size for this client when not specified.

        Returns:
            Number of items to sync per batch (default)
        """
        pass

    @abstractmethod
    def get_max_window_size(self) -> int:
        """
        Maximum allowed batch size for this client.

        Returns:
            Maximum number of items to sync per batch
        """
        pass

    @abstractmethod
    def get_body_type_preference_order(self) -> List[int]:
        """
        Preferred body types in order of preference.

        Returns:
            List of body type integers in order: 1=plain, 2=HTML, 4=MIME

        Example:
            Outlook: [4, 1, 2] - prefers MIME, then plain, then HTML
            iOS: [1, 2, 4] - prefers plain, then HTML, then MIME
        """
        pass

    @abstractmethod
    def should_use_pending_confirmation(self) -> bool:
        """
        Whether to use two-phase commit (pending confirmation) for this client.

        Returns:
            True if client should confirm receipt before marking items synced

        Note:
            Z-Push/Grommunio use two-phase commit for all clients for reliability
        """
        pass

    @abstractmethod
    def get_truncation_strategy(
        self,
        body_type: int,
        truncation_size: Optional[int],
        is_initial_sync: bool,
    ) -> Optional[int]:
        """
        Calculate effective truncation size for this client.

        Args:
            body_type: 1=plain, 2=HTML, 4=MIME
            truncation_size: Client's requested truncation size (None = unlimited)
            is_initial_sync: True if this is the initial sync (SyncKey=0)

        Returns:
            Effective truncation size in bytes, or None for unlimited

        Z-Push Strategy:
            - Type 1/2: Honor client's request exactly (no override)
            - Type 4 (MIME): Cap at 512KB to prevent huge transfers
        """
        pass

    def get_client_name(self) -> str:
        """
        Human-readable name for this client type.

        Returns:
            Client name (e.g., "Outlook", "iOS", "Android")
        """
        return self.__class__.__name__.replace("Strategy", "")
