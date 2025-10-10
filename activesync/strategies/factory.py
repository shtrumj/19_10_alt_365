"""
ActiveSync Strategy Factory

Factory function to create the appropriate strategy based on client type detection.

Client Detection Logic:
- Outlook: User-Agent contains "Outlook" OR DeviceType contains "WindowsOutlook"
- iOS: User-Agent contains "iPhone" OR "iPad"
- Android: User-Agent contains "Android"
- Default: iOS strategy (most permissive)
"""

from .android_strategy import AndroidStrategy
from .base import ActiveSyncStrategy
from .ios_strategy import IOSStrategy
from .outlook_strategy import OutlookStrategy


def get_activesync_strategy(user_agent: str, device_type: str) -> ActiveSyncStrategy:
    """
    Factory to create appropriate strategy based on client type.

    Args:
        user_agent: HTTP User-Agent header value
        device_type: ActiveSync DeviceType query parameter

    Returns:
        Appropriate ActiveSyncStrategy instance for the client

    Example:
        >>> strategy = get_activesync_strategy("Outlook/16.0", "WindowsOutlook15")
        >>> isinstance(strategy, OutlookStrategy)
        True

        >>> strategy = get_activesync_strategy("Apple iPhone13,2", "iPhone")
        >>> isinstance(strategy, IOSStrategy)
        True
    """
    ua_lower = user_agent.lower()
    dt_lower = device_type.lower()

    # Outlook Desktop detection
    if "outlook" in ua_lower or "windowsoutlook" in dt_lower:
        return OutlookStrategy()

    # iOS detection (iPhone, iPad, iPod)
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        return IOSStrategy()

    # Android detection
    elif "android" in ua_lower:
        return AndroidStrategy()

    # Default fallback: Use iOS strategy (most permissive)
    # This handles unknown clients gracefully
    else:
        return IOSStrategy()


def detect_client_type(user_agent: str, device_type: str) -> str:
    """
    Helper function to detect client type as string.

    Args:
        user_agent: HTTP User-Agent header value
        device_type: ActiveSync DeviceType query parameter

    Returns:
        Client type string: "Outlook", "iOS", "Android", or "Unknown"
    """
    strategy = get_activesync_strategy(user_agent, device_type)
    return strategy.get_client_name()
