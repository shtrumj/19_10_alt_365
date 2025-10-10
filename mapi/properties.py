"""
MAPI Property System

High-level interface for working with MAPI properties.
Handles property storage, retrieval, and conversion.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .binary import PropertyValue
from .constants import *


class PropertyStore:
    """
    In-memory property store for MAPI objects.

    Provides a dictionary-like interface for property access.
    """

    def __init__(self, initial_properties: Dict[int, Any] = None):
        self._properties: Dict[int, Any] = initial_properties or {}

    def get(self, prop_tag: int, default: Any = None) -> Any:
        """Get property value."""
        return self._properties.get(prop_tag, default)

    def set(self, prop_tag: int, value: Any):
        """Set property value."""
        self._properties[prop_tag] = value

    def delete(self, prop_tag: int):
        """Delete property."""
        if prop_tag in self._properties:
            del self._properties[prop_tag]

    def get_all(self) -> Dict[int, Any]:
        """Get all properties."""
        return self._properties.copy()

    def get_tags(self) -> List[int]:
        """Get all property tags."""
        return list(self._properties.keys())

    def has(self, prop_tag: int) -> bool:
        """Check if property exists."""
        return prop_tag in self._properties

    def to_property_values(self, tags: List[int] = None) -> List[PropertyValue]:
        """
        Convert to list of PropertyValue objects.

        If tags is provided, only returns those properties.
        """
        if tags is None:
            tags = self.get_tags()

        result = []
        for tag in tags:
            if tag in self._properties:
                result.append(PropertyValue(tag, self._properties[tag]))

        return result

    def from_property_values(self, prop_values: List[PropertyValue]):
        """Load from list of PropertyValue objects."""
        for prop in prop_values:
            self._properties[prop.prop_tag] = prop.value

    def to_json(self) -> str:
        """Serialize to JSON."""
        # Convert property tags to strings for JSON
        json_dict = {}
        for tag, value in self._properties.items():
            # Convert datetime to ISO format
            if isinstance(value, datetime):
                value = value.isoformat()
            # Convert bytes to hex
            elif isinstance(value, bytes):
                value = value.hex()
            json_dict[f"0x{tag:08X}"] = value

        return json.dumps(json_dict)

    @staticmethod
    def from_json(json_str: str) -> "PropertyStore":
        """Deserialize from JSON."""
        json_dict = json.loads(json_str)
        properties = {}

        for tag_str, value in json_dict.items():
            # Convert string tag back to int
            tag = int(tag_str, 16)

            # Try to restore datetime
            if isinstance(value, str) and "T" in value:
                try:
                    value = datetime.fromisoformat(value)
                except:
                    pass

            properties[tag] = value

        return PropertyStore(properties)


def create_folder_properties(
    folder_id: int,
    display_name: str,
    parent_id: int = 0,
    folder_type: int = FOLDER_GENERIC,
    container_class: str = IPF_NOTE,
    content_count: int = 0,
    unread_count: int = 0,
    has_subfolders: bool = False,
) -> PropertyStore:
    """Create property store for a folder."""
    store = PropertyStore()

    # Core properties
    store.set(PR_ENTRYID, folder_id.to_bytes(8, "little"))
    store.set(PR_PARENT_ENTRYID, parent_id.to_bytes(8, "little"))
    store.set(PR_DISPLAY_NAME, display_name)
    store.set(PR_FOLDER_TYPE, folder_type)
    store.set(PR_CONTAINER_CLASS, container_class)
    store.set(PR_CONTENT_COUNT, content_count)
    store.set(PR_CONTENT_UNREAD, unread_count)
    store.set(PR_SUBFOLDERS, has_subfolders)
    store.set(PR_OBJECT_TYPE, MAPI_FOLDER)

    # Timestamps
    now = datetime.utcnow()
    store.set(PR_CREATION_TIME, now)
    store.set(PR_LAST_MODIFICATION_TIME, now)

    return store


def create_message_properties(
    message_id: int,
    folder_id: int,
    subject: str,
    body: str = "",
    html_body: str = None,
    sender_name: str = "",
    sender_email: str = "",
    message_class: str = IPM_NOTE,
    received_time: datetime = None,
    is_read: bool = False,
    has_attachments: bool = False,
) -> PropertyStore:
    """Create property store for a message."""
    store = PropertyStore()

    # Core properties
    store.set(PR_ENTRYID, message_id.to_bytes(8, "little"))
    store.set(PR_PARENT_ENTRYID, folder_id.to_bytes(8, "little"))
    store.set(PR_MESSAGE_CLASS, message_class)
    store.set(PR_SUBJECT, subject)
    store.set(PR_BODY, body)

    if html_body:
        store.set(PR_HTML, html_body.encode("utf-8"))

    # Sender info
    store.set(PR_SENDER_NAME, sender_name)
    store.set(PR_SENDER_EMAIL_ADDRESS, sender_email)

    # Flags
    flags = 0
    if is_read:
        flags |= MSGFLAG_READ
    if has_attachments:
        flags |= MSGFLAG_HASATTACH
    store.set(PR_MESSAGE_FLAGS, flags)
    store.set(PR_HASATTACH, has_attachments)

    # Timestamps
    now = datetime.utcnow()
    store.set(PR_CREATION_TIME, now)
    store.set(PR_LAST_MODIFICATION_TIME, now)
    store.set(PR_MESSAGE_DELIVERY_TIME, received_time or now)
    store.set(PR_CLIENT_SUBMIT_TIME, received_time or now)

    # Size (approximate)
    size = len(subject) + len(body)
    if html_body:
        size += len(html_body)
    store.set(PR_MESSAGE_SIZE, size)

    store.set(PR_OBJECT_TYPE, MAPI_MESSAGE)

    return store


def create_attachment_properties(
    attachment_id: int,
    filename: str,
    size: int,
    mime_type: str = "application/octet-stream",
    is_inline: bool = False,
) -> PropertyStore:
    """Create property store for an attachment."""
    store = PropertyStore()

    store.set(PR_ATTACH_NUM, attachment_id)
    store.set(PR_ATTACH_FILENAME, filename)
    store.set(PR_ATTACH_LONG_FILENAME, filename)
    store.set(PR_ATTACH_SIZE, size)
    store.set(PR_ATTACH_MIME_TAG, mime_type)
    store.set(PR_ATTACH_METHOD, 1)  # ATTACH_BY_VALUE
    store.set(PR_OBJECT_TYPE, MAPI_ATTACH)

    return store


def get_property_name(prop_tag: int) -> str:
    """Get human-readable name for property tag."""
    # Map of common property tags to names
    TAG_NAMES = {
        PR_ENTRYID: "PR_ENTRYID",
        PR_DISPLAY_NAME: "PR_DISPLAY_NAME",
        PR_SUBJECT: "PR_SUBJECT",
        PR_MESSAGE_CLASS: "PR_MESSAGE_CLASS",
        PR_BODY: "PR_BODY",
        PR_HTML: "PR_HTML",
        PR_SENDER_NAME: "PR_SENDER_NAME",
        PR_SENDER_EMAIL_ADDRESS: "PR_SENDER_EMAIL_ADDRESS",
        PR_FOLDER_TYPE: "PR_FOLDER_TYPE",
        PR_CONTENT_COUNT: "PR_CONTENT_COUNT",
        PR_CONTENT_UNREAD: "PR_CONTENT_UNREAD",
        PR_CONTAINER_CLASS: "PR_CONTAINER_CLASS",
        PR_MESSAGE_FLAGS: "PR_MESSAGE_FLAGS",
        PR_HASATTACH: "PR_HASATTACH",
        PR_PARENT_ENTRYID: "PR_PARENT_ENTRYID",
    }

    if prop_tag in TAG_NAMES:
        return TAG_NAMES[prop_tag]

    prop_id = (prop_tag >> 16) & 0xFFFF
    prop_type = prop_tag & 0xFFFF
    type_name = PROPERTY_TYPE_NAMES.get(prop_type, f"0x{prop_type:04X}")
    return f"0x{prop_id:04X}:{type_name}"
