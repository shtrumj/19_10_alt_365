#!/usr/bin/env python3
"""
Fix iOS 26 headers in router.py
"""

import re

def fix_router_headers():
    """Fix the router file to use iOS 26 headers properly."""
    
    with open('/Users/jonathanshtrum/Downloads/365/activesync/router.py', 'r') as f:
        content = f.read()
    
    # Fix the first _eas_options_headers function
    pattern1 = r'def _eas_options_headers\(\) -> dict:\s*"""Headers for OPTIONS discovery - iOS 26 compatible with ActiveSync 16\.1\."""\s*return get_ios26_options_headers\(\)\s*"Server": "365-Email-System",.*?}'
    
    replacement1 = '''def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery - iOS 26 compatible with ActiveSync 16.1."""
    return get_ios26_options_headers()'''
    
    content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)
    
    # Fix the second _eas_options_headers function
    pattern2 = r'def _eas_options_headers\(\) -> dict:\s*"""Headers for OPTIONS discovery only.*?"""\s*return \{\s*# MS-ASHTTP required headers\s*"MS-Server-ActiveSync": "15\.0",.*?}'
    
    replacement2 = '''def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery - iOS 26 compatible with ActiveSync 16.1."""
    return get_ios26_options_headers()'''
    
    content = re.sub(pattern2, replacement2, content, flags=re.DOTALL)
    
    # Fix the first _eas_headers function
    pattern3 = r'def _eas_headers\(policy_key: str = None, protocol_version: str = None\) -> dict:\s*"""Headers for ActiveSync command responses \(POST\) - iOS 26 compatible\."""\s*return create_ios26_compatibility_headers\(\s*user_agent="",.*?\)'
    
    replacement3 = '''def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST) - iOS 26 compatible."""
    return create_ios26_compatibility_headers(
        user_agent="",  # Will be passed from request context
        policy_key=policy_key,
        protocol_version=protocol_version
    )'''
    
    content = re.sub(pattern3, replacement3, content, flags=re.DOTALL)
    
    # Fix the second _eas_headers function
    pattern4 = r'def _eas_headers\(policy_key: str = None, protocol_version: str = None\) -> dict:\s*"""Headers for ActiveSync command responses \(POST\)\..*?"""\s*headers = \{\s*# MS-ASHTTP required headers\s*"MS-Server-ActiveSync": "14\.1",.*?}'
    
    replacement4 = '''def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST) - iOS 26 compatible."""
    return create_ios26_compatibility_headers(
        user_agent="",  # Will be passed from request context
        policy_key=policy_key,
        protocol_version=protocol_version
    )'''
    
    content = re.sub(pattern4, replacement4, content, flags=re.DOTALL)
    
    with open('/Users/jonathanshtrum/Downloads/365/activesync/router.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed iOS 26 headers in router.py")

if __name__ == "__main__":
    fix_router_headers()
