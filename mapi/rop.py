"""
MAPI ROP (Remote Operations) Implementation

Handles parsing and execution of ROP commands.

Reference: MS-OXCROPS (Remote Operations Protocol)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .binary import BinaryReader, BinaryWriter, PropertyValue
from .constants import *

logger = logging.getLogger(__name__)


# ============================================================================
# ROP Request/Response Structures
# ============================================================================


@dataclass
class RopRequest:
    """Base class for ROP requests."""

    rop_id: int
    handle_index: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopRequest":
        """Parse ROP request from binary."""
        raise NotImplementedError(f"Parse not implemented for {cls.__name__}")

    def __repr__(self):
        rop_name = ROP_NAMES.get(self.rop_id, f"Unknown(0x{self.rop_id:02X})")
        return f"<{self.__class__.__name__} rop={rop_name} handle={self.handle_index}>"


@dataclass
class RopResponse:
    """Base class for ROP responses."""

    rop_id: int
    handle_index: int
    error_code: int

    def encode(self) -> bytes:
        """Encode ROP response to binary."""
        raise NotImplementedError(
            f"Encode not implemented for {self.__class__.__name__}"
        )

    def __repr__(self):
        rop_name = ROP_NAMES.get(self.rop_id, f"Unknown(0x{self.rop_id:02X})")
        status = (
            "SUCCESS"
            if self.error_code == SUCCESS
            else f"ERROR(0x{self.error_code:08X})"
        )
        return f"<{self.__class__.__name__} rop={rop_name} status={status}>"


# ============================================================================
# ROP Buffer Parser
# ============================================================================


class RopBuffer:
    """
    ROP buffer container.

    Contains multiple ROP operations to be executed atomically.

    Reference: MS-OXCROPS Section 2.2.1.1
    """

    def __init__(self, rop_list: List[RopRequest] = None):
        self.rop_list = rop_list or []

    @staticmethod
    def parse(data: bytes) -> "RopBuffer":
        """
        Parse ROP buffer from binary.

        Format:
          - ROP Size (2 bytes)
          - ROP Count (2 bytes)
          - ROP Array (variable)
        """
        reader = BinaryReader(data)

        # Read ROP buffer header
        rop_size = reader.read_uint16()
        rop_count = reader.read_uint16()

        logger.info(f"Parsing ROP buffer: size={rop_size} count={rop_count}")

        rop_list = []
        for i in range(rop_count):
            try:
                # Read ROP ID
                rop_id = reader.read_byte()
                rop_name = ROP_NAMES.get(rop_id, f"Unknown(0x{rop_id:02X})")

                logger.debug(f"Parsing ROP {i+1}/{rop_count}: {rop_name}")

                # Parse ROP based on ID
                rop = parse_rop_request(rop_id, reader)
                rop_list.append(rop)

            except Exception as e:
                logger.error(f"Failed to parse ROP {i+1}/{rop_count}: {e}")
                # Skip this ROP and continue
                continue

        return RopBuffer(rop_list)

    def encode_response(self, responses: List[RopResponse]) -> bytes:
        """
        Encode ROP response buffer.

        Format:
          - ROP Size (2 bytes)
          - ROP Count (2 bytes)
          - ROP Array (variable)
        """
        writer = BinaryWriter()

        # Reserve space for size
        size_position = writer.tell()
        writer.write_uint16(0)  # Placeholder

        # Write ROP count
        writer.write_uint16(len(responses))

        # Write each ROP response
        for response in responses:
            response_data = response.encode()
            writer.write_bytes(response_data)

        # Update size
        total_size = writer.tell()
        current_pos = writer.tell()
        writer.stream.seek(size_position)
        writer.write_uint16(total_size - 2)  # Size doesn't include itself
        writer.stream.seek(current_pos)

        return writer.get_bytes()


def parse_rop_request(rop_id: int, reader: BinaryReader) -> RopRequest:
    """
    Parse a single ROP request.

    Dispatches to specific ROP parser based on ROP ID.
    """

    if rop_id == ROP_LOGON:
        return RopLogonRequest.parse(reader)

    elif rop_id == ROP_GET_HIERARCHY_TABLE:
        return RopGetHierarchyTableRequest.parse(reader)

    elif rop_id == ROP_GET_CONTENTS_TABLE:
        return RopGetContentsTableRequest.parse(reader)

    elif rop_id == ROP_SET_COLUMNS:
        return RopSetColumnsRequest.parse(reader)

    elif rop_id == ROP_QUERY_ROWS:
        return RopQueryRowsRequest.parse(reader)

    elif rop_id == ROP_OPEN_FOLDER:
        return RopOpenFolderRequest.parse(reader)

    elif rop_id == ROP_OPEN_MESSAGE:
        return RopOpenMessageRequest.parse(reader)

    elif rop_id == ROP_GET_PROPERTIES_SPECIFIC:
        return RopGetPropertiesSpecificRequest.parse(reader)

    elif rop_id == ROP_RELEASE:
        return RopReleaseRequest.parse(reader)

    else:
        logger.warning(f"Unknown ROP ID: 0x{rop_id:02X}")
        raise NotImplementedError(f"ROP 0x{rop_id:02X} not implemented")


# ============================================================================
# Specific ROP Implementations
# ============================================================================


@dataclass
class RopLogonRequest(RopRequest):
    """
    RopLogon request (MS-OXCROPS Section 2.2.3.1)

    Establishes a session with the message store.
    """

    logon_flags: int
    open_flags: int
    store_state: int
    essdn: str  # Distinguished name

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopLogonRequest":
        handle_index = reader.read_byte()
        logon_flags = reader.read_byte()
        open_flags = reader.read_uint32()
        store_state = reader.read_uint32()

        # Read ESSDN (null-terminated string)
        essdn_length = reader.read_uint16()
        essdn = reader.read_string_ascii(essdn_length) if essdn_length > 0 else ""

        return cls(
            rop_id=ROP_LOGON,
            handle_index=handle_index,
            logon_flags=logon_flags,
            open_flags=open_flags,
            store_state=store_state,
            essdn=essdn,
        )


@dataclass
class RopLogonResponse(RopResponse):
    """RopLogon response."""

    logon_flags: int
    folder_ids: List[int]  # Well-known folder IDs

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_byte(self.logon_flags)

            # Write folder IDs (13 well-known folders)
            # Inbox, Drafts, Sent Items, etc.
            writer.write_uint16(len(self.folder_ids))
            for folder_id in self.folder_ids:
                writer.write_uint64(folder_id)

        return writer.get_bytes()


@dataclass
class RopGetHierarchyTableRequest(RopRequest):
    """
    RopGetHierarchyTable request (MS-OXCROPS Section 2.2.4.2)

    Gets folder hierarchy table.
    """

    table_flags: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopGetHierarchyTableRequest":
        handle_index = reader.read_byte()
        table_flags = reader.read_byte()

        return cls(
            rop_id=ROP_GET_HIERARCHY_TABLE,
            handle_index=handle_index,
            table_flags=table_flags,
        )


@dataclass
class RopGetHierarchyTableResponse(RopResponse):
    """RopGetHierarchyTable response."""

    row_count: int

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_uint32(self.row_count)

        return writer.get_bytes()


@dataclass
class RopGetContentsTableRequest(RopRequest):
    """
    RopGetContentsTable request (MS-OXCROPS Section 2.2.4.3)

    Gets folder contents table.
    """

    table_flags: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopGetContentsTableRequest":
        handle_index = reader.read_byte()
        table_flags = reader.read_byte()

        return cls(
            rop_id=ROP_GET_CONTENTS_TABLE,
            handle_index=handle_index,
            table_flags=table_flags,
        )


@dataclass
class RopGetContentsTableResponse(RopResponse):
    """RopGetContentsTable response."""

    row_count: int

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_uint32(self.row_count)

        return writer.get_bytes()


@dataclass
class RopSetColumnsRequest(RopRequest):
    """
    RopSetColumns request (MS-OXCROPS Section 2.2.5.1)

    Sets columns for table query.
    """

    set_column_flags: int
    property_tags: List[int]

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopSetColumnsRequest":
        handle_index = reader.read_byte()
        set_column_flags = reader.read_byte()

        # Read property tags
        property_tag_count = reader.read_uint16()
        property_tags = []
        for _ in range(property_tag_count):
            property_tags.append(reader.read_uint32())

        return cls(
            rop_id=ROP_SET_COLUMNS,
            handle_index=handle_index,
            set_column_flags=set_column_flags,
            property_tags=property_tags,
        )


@dataclass
class RopSetColumnsResponse(RopResponse):
    """RopSetColumns response."""

    table_status: int

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_byte(self.table_status)  # TBLSTAT_COMPLETE

        return writer.get_bytes()


@dataclass
class RopQueryRowsRequest(RopRequest):
    """
    RopQueryRows request (MS-OXCROPS Section 2.2.5.4)

    Queries rows from table.
    """

    query_rows_flags: int
    forward_read: bool
    row_count: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopQueryRowsRequest":
        handle_index = reader.read_byte()
        query_rows_flags = reader.read_byte()
        forward_read = reader.read_byte() != 0
        row_count = reader.read_uint16()

        return cls(
            rop_id=ROP_QUERY_ROWS,
            handle_index=handle_index,
            query_rows_flags=query_rows_flags,
            forward_read=forward_read,
            row_count=row_count,
        )


@dataclass
class RopQueryRowsResponse(RopResponse):
    """RopQueryRows response."""

    origin: int
    row_data: List[List[PropertyValue]]

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_byte(self.origin)  # BOOKMARK_BEGINNING = 0
            writer.write_uint16(len(self.row_data))  # Row count

            # Write each row
            for row in self.row_data:
                # Write property count
                writer.write_uint16(len(row))

                # Write each property
                for prop in row:
                    writer.write_bytes(prop.encode())

        return writer.get_bytes()


@dataclass
class RopOpenFolderRequest(RopRequest):
    """
    RopOpenFolder request (MS-OXCROPS Section 2.2.4.1)

    Opens a folder.
    """

    folder_id: int
    open_mode_flags: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopOpenFolderRequest":
        handle_index = reader.read_byte()
        folder_id = reader.read_uint64()
        open_mode_flags = reader.read_byte()

        return cls(
            rop_id=ROP_OPEN_FOLDER,
            handle_index=handle_index,
            folder_id=folder_id,
            open_mode_flags=open_mode_flags,
        )


@dataclass
class RopOpenFolderResponse(RopResponse):
    """RopOpenFolder response."""

    has_rules: bool
    is_ghost: bool

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_byte(1 if self.has_rules else 0)
            writer.write_byte(1 if self.is_ghost else 0)

        return writer.get_bytes()


@dataclass
class RopOpenMessageRequest(RopRequest):
    """
    RopOpenMessage request (MS-OXCROPS Section 2.2.6.1)

    Opens a message.
    """

    folder_id: int
    message_id: int
    code_page_id: int
    open_mode_flags: int

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopOpenMessageRequest":
        handle_index = reader.read_byte()
        folder_id = reader.read_uint64()
        message_id = reader.read_uint64()
        code_page_id = reader.read_uint16()
        open_mode_flags = reader.read_byte()

        return cls(
            rop_id=ROP_OPEN_MESSAGE,
            handle_index=handle_index,
            folder_id=folder_id,
            message_id=message_id,
            code_page_id=code_page_id,
            open_mode_flags=open_mode_flags,
        )


@dataclass
class RopOpenMessageResponse(RopResponse):
    """RopOpenMessage response."""

    has_named_properties: bool
    subject_prefix: str
    normalized_subject: str
    recipient_count: int
    recipient_columns: List[int]

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            writer.write_byte(1 if self.has_named_properties else 0)
            writer.write_string_ascii(self.subject_prefix or "", null_terminate=True)
            writer.write_string_ascii(
                self.normalized_subject or "", null_terminate=True
            )
            writer.write_uint16(self.recipient_count)
            writer.write_uint16(len(self.recipient_columns))
            for col in self.recipient_columns:
                writer.write_uint32(col)

        return writer.get_bytes()


@dataclass
class RopGetPropertiesSpecificRequest(RopRequest):
    """
    RopGetPropertiesSpecific request (MS-OXCROPS Section 2.2.8.1)

    Gets specific properties from object.
    """

    property_size_limit: int
    want_unicode: bool
    property_tags: List[int]

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopGetPropertiesSpecificRequest":
        handle_index = reader.read_byte()
        property_size_limit = reader.read_uint16()
        want_unicode = reader.read_uint16() != 0

        # Read property tags
        property_tag_count = reader.read_uint16()
        property_tags = []
        for _ in range(property_tag_count):
            property_tags.append(reader.read_uint32())

        return cls(
            rop_id=ROP_GET_PROPERTIES_SPECIFIC,
            handle_index=handle_index,
            property_size_limit=property_size_limit,
            want_unicode=want_unicode,
            property_tags=property_tags,
        )


@dataclass
class RopGetPropertiesSpecificResponse(RopResponse):
    """RopGetPropertiesSpecific response."""

    row_data: List[PropertyValue]

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        if self.error_code == SUCCESS:
            # Write property row
            writer.write_uint16(len(self.row_data))
            for prop in self.row_data:
                writer.write_bytes(prop.encode())

        return writer.get_bytes()


@dataclass
class RopReleaseRequest(RopRequest):
    """
    RopRelease request (MS-OXCROPS Section 2.2.2.1)

    Releases an object handle.
    """

    @classmethod
    def parse(cls, reader: BinaryReader) -> "RopReleaseRequest":
        handle_index = reader.read_byte()

        return cls(rop_id=ROP_RELEASE, handle_index=handle_index)


@dataclass
class RopReleaseResponse(RopResponse):
    """RopRelease response."""

    def encode(self) -> bytes:
        writer = BinaryWriter()
        writer.write_byte(self.rop_id)
        writer.write_byte(self.handle_index)
        writer.write_uint32(self.error_code)

        return writer.get_bytes()
