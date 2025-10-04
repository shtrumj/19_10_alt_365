#!/usr/bin/env python3
"""
iOS 26 ActiveSync Router Patch

This script updates the ActiveSync router to use iOS 26 compatibility features.
"""

import re

def patch_router_file():
    """Apply iOS 26 compatibility patches to the router file."""
    
    # Read the current router file
    with open('/Users/jonathanshtrum/Downloads/365/activesync/router.py', 'r') as f:
        content = f.read()
    
    # Add iOS 26 imports after existing imports
    import_pattern = r'(from app\.synckey_utils import parse_synckey, generate_synckey, bump_synckey, has_synckey)'
    replacement = r'''\1

# iOS 26 compatibility module
from .ios26_compatibility import (
    get_ios26_options_headers,
    get_ios26_response_headers,
    get_ios26_sync_headers,
    get_ios26_ping_headers,
    detect_ios26_client,
    get_ios26_optimized_heartbeat_interval,
    create_ios26_compatibility_headers
)'''
    
    content = re.sub(import_pattern, replacement, content)
    
    # Update the first _eas_options_headers function
    options_pattern = r'(def _eas_options_headers\(\) -> dict:\s*"""Headers for OPTIONS discovery only.*?"""\s*return \{\s*# MS-ASHTTP required headers\s*"MS-Server-ActiveSync": "15\.0",)'
    options_replacement = r'''def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery - iOS 26 compatible with ActiveSync 16.1."""
    return get_ios26_options_headers()'''
    
    content = re.sub(options_pattern, options_replacement, content, flags=re.DOTALL)
    
    # Update the first _eas_headers function
    headers_pattern = r'(def _eas_headers\(policy_key: str = None, protocol_version: str = None\) -> dict:\s*"""Headers for ActiveSync command responses.*?"""\s*headers = \{\s*# MS-ASHTTP required headers\s*"MS-Server-ActiveSync": "14\.1",)'
    headers_replacement = r'''def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST) - iOS 26 compatible."""
    return create_ios26_compatibility_headers(
        user_agent="",  # Will be passed from request context
        policy_key=policy_key,
        protocol_version=protocol_version
    )'''
    
    content = re.sub(headers_pattern, headers_replacement, content, flags=re.DOTALL)
    
    # Write the updated content back
    with open('/Users/jonathanshtrum/Downloads/365/activesync/router.py', 'w') as f:
        f.write(content)
    
    print("✅ iOS 26 compatibility patches applied to router.py")

if __name__ == "__main__":
    patch_router_file()
