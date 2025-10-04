#!/usr/bin/env python3
"""Fix imports in activesync/router.py"""

import re

# Read the file
with open('activesync/router.py', 'r') as f:
    content = f.read()

# Fix imports - replace relative imports with absolute app imports
replacements = [
    (r'from \.\.auth import', 'from app.auth import'),
    (r'from \.\.database import', 'from app.database import'),
    (r'from \.\.diagnostic_logger import', 'from app.diagnostic_logger import'),
    (r'from \.\.email_service import', 'from app.email_service import'),
    (r'from \.\.wbxml_parser import', 'from app.wbxml_parser import'),
    (r'from \.\.synckey_utils import', 'from app.synckey_utils import'),
    (r'from activesync\.wbxml_builder import', 'from .wbxml_builder import'),
    (r'from activesync\.state_machine import', 'from .state_machine import'),
    (r'from activesync\.adapter import', 'from .adapter import'),
    (r'from \.\.push_notifications import', 'from app.push_notifications import'),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open('activesync/router.py', 'w') as f:
    f.write(content)

print("✅ Fixed imports in activesync/router.py")






