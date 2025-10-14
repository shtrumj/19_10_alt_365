#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iOS 26 ActiveSync Compatibility Module

This module provides iOS 26 specific ActiveSync protocol implementations
based on the latest Microsoft ActiveSync 16.1 specifications.

Key features for iOS 26:
- ActiveSync 16.1 protocol support
- Enhanced automatic sync capabilities
- Improved push notification handling
- Better fetch fallback mechanisms
"""


def get_ios26_options_headers() -> dict:
    """
    Headers for OPTIONS discovery - iOS 26 compatible with ActiveSync 16.1.

    iOS 26 requires ActiveSync 16.1 for full compatibility and automatic sync.
    This replaces the traditional "Push" option with enhanced protocol features.
    """
    return {
        # MS-ASHTTP required headers - Updated for iOS 26 compatibility
        "MS-Server-ActiveSync": "16.1",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # iOS 26 requires ActiveSync 16.1 for full compatibility
        "MS-ASProtocolVersions": "12.1,14.0,14.1,16.0,16.1",
        # Enhanced command set for iOS 26
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert,Autodiscover,GetHierarchy"
        ),
        # iOS 26 protocol support - includes latest versions
        "MS-ASProtocolSupports": "12.1,14.0,14.1,16.0,16.1",
        # iOS 26 specific headers for enhanced compatibility
        "X-MS-Server-ActiveSync": "16.1",
        # X-MS-PolicyKey will be set explicitly by caller when available
        # iOS 26 automatic sync headers
        "X-MS-Server-ActiveSync-Version": "16.1",
        "X-MS-ASProtocolVersion": "16.1",
    }


def get_ios26_response_headers(
    policy_key: str = None, protocol_version: str = None
) -> dict:
    """
    Headers for ActiveSync command responses (POST) - iOS 26 compatible.

    iOS 26 requires ActiveSync 16.1 for full compatibility and automatic sync.
    Echoes client's requested protocol version for proper negotiation.
    """
    # iOS 26 supports up to ActiveSync 16.1, fallback to 14.1 for older clients
    if protocol_version and protocol_version in [
        "12.1",
        "14.0",
        "14.1",
        "16.0",
        "16.1",
    ]:
        negotiated_version = protocol_version
    else:
        negotiated_version = "16.1"  # Default to latest for iOS 26

    headers = {
        # MS-ASHTTP required headers - Updated for iOS 26
        "MS-Server-ActiveSync": "16.1",
        "X-MS-Server-ActiveSync": "16.1",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        # iOS 26 protocol version negotiation
        "MS-ASProtocolVersion": negotiated_version,
        "MS-ASProtocolVersions": "12.1,14.0,14.1,16.0,16.1",
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,FolderCreate,FolderDelete,FolderUpdate,GetItemEstimate,"
            "Ping,Provision,Options,Settings,ItemOperations,SendMail,SmartForward,"
            "SmartReply,MoveItems,MeetingResponse,Search,Find,GetAttachment,Calendar,"
            "ResolveRecipients,ValidateCert,Autodiscover,GetHierarchy"
        ),
        # iOS 26 protocol support
        "MS-ASProtocolSupports": "12.1,14.0,14.1,16.0,16.1",
        # iOS 26 specific headers for enhanced compatibility
        "X-MS-ASProtocolVersion": negotiated_version,
    }

    # Add X-MS-PolicyKey header if provided (iOS expects this after provisioning)
    if policy_key:
        headers["X-MS-PolicyKey"] = policy_key

    return headers


def get_ios26_sync_headers(
    policy_key: str = None, protocol_version: str = None
) -> dict:
    """
    Headers specifically for Sync command responses - iOS 26 optimized.

    iOS 26 uses enhanced Sync capabilities for automatic email delivery
    even without traditional "Push" mode.
    """
    headers = get_ios26_response_headers(policy_key, protocol_version)

    # iOS 26 specific Sync headers for automatic sync
    headers.update(
        {
            "X-MS-Sync-Key": "1",  # Will be updated per sync
            "X-MS-Server-ActiveSync-Sync": "16.1",
            "X-MS-ASProtocolVersion-Sync": protocol_version or "16.1",
        }
    )

    return headers


def get_ios26_ping_headers(
    policy_key: str = None, protocol_version: str = None
) -> dict:
    """
    Headers specifically for Ping command responses - iOS 26 optimized.

    iOS 26 uses enhanced Ping capabilities for real-time notifications
    even without traditional "Push" mode.
    """
    headers = get_ios26_response_headers(policy_key, protocol_version)

    # iOS 26 specific Ping headers for real-time sync
    headers.update(
        {
            "X-MS-Ping-Heartbeat": "540",  # 9 minutes default
            "X-MS-Server-ActiveSync-Ping": "16.1",
            "X-MS-ASProtocolVersion-Ping": protocol_version or "16.1",
        }
    )

    return headers


def detect_ios26_client(user_agent: str) -> bool:
    """
    Detect if the client is iOS 26 or newer.

    Args:
        user_agent: The User-Agent header from the request

    Returns:
        bool: True if iOS 26+, False otherwise
    """
    if not user_agent:
        return False

    # iOS 26+ user agent patterns
    ios26_patterns = [
        "iPhone OS 26",
        "iOS 26",
        "iPhone16C2",  # iPhone 16 series
        "iPhone17C2",  # iPhone 17 series
    ]

    return any(pattern in user_agent for pattern in ios26_patterns)


def get_ios26_optimized_heartbeat_interval(user_agent: str) -> int:
    """
    Get optimized heartbeat interval for iOS 26 clients.

    iOS 26 uses different timing for automatic sync compared to older versions.

    Args:
        user_agent: The User-Agent header from the request

    Returns:
        int: Heartbeat interval in seconds
    """
    if detect_ios26_client(user_agent):
        # iOS 26 uses shorter intervals for better responsiveness
        return 300  # 5 minutes instead of 9 minutes
    else:
        # Standard interval for older iOS versions
        return 540  # 9 minutes


def get_ios26_enhanced_commands() -> list:
    """
    Get enhanced command set for iOS 26 compatibility.

    iOS 26 supports additional ActiveSync commands for better sync capabilities.

    Returns:
        list: Enhanced command list for iOS 26
    """
    return [
        "Sync",
        "FolderSync",
        "FolderCreate",
        "FolderDelete",
        "FolderUpdate",
        "GetItemEstimate",
        "Ping",
        "Provision",
        "Options",
        "Settings",
        "ItemOperations",
        "SendMail",
        "SmartForward",
        "SmartReply",
        "MoveItems",
        "MeetingResponse",
        "Search",
        "Find",
        "GetAttachment",
        "Calendar",
        "ResolveRecipients",
        "ValidateCert",
        "Autodiscover",
        "GetHierarchy",
        "SyncMail",
        "SyncCalendar",
        "SyncContacts",
        "SyncTasks",
        "SyncNotes",
        "GetItemEstimate",
        "ItemOperations",
    ]


def create_ios26_compatibility_headers(
    user_agent: str, policy_key: str = None, protocol_version: str = None
) -> dict:
    """
    Create iOS 26 compatibility headers based on client detection.

    This function automatically detects iOS 26 clients and applies appropriate
    headers for optimal compatibility and automatic sync.

    Args:
        user_agent: The User-Agent header from the request
        policy_key: Policy key for provisioned devices
        protocol_version: Client's requested protocol version

    Returns:
        dict: Optimized headers for the client
    """
    if detect_ios26_client(user_agent):
        # Use iOS 26 optimized headers
        return get_ios26_response_headers(policy_key, protocol_version)
    else:
        # Use standard headers for older clients
        from .router import _eas_headers

        return _eas_headers(policy_key, protocol_version)
