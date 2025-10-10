"""
MAPI Binary Serialization Framework

Handles binary encoding/decoding for MAPI/HTTP protocol.
All MAPI data structures use little-endian byte order.

Reference: MS-OXCDATA Section 2.11 (Data Structures)
"""

import io
import struct
import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

from .constants import *


class BinaryReader:
    """
    Binary reader for MAPI data structures.

    All reads are little-endian unless otherwise specified.
    """

    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)
        self.length = len(data)

    def tell(self) -> int:
        """Get current position in stream."""
        return self.stream.tell()

    def seek(self, position: int):
        """Seek to position in stream."""
        self.stream.seek(position)

    def remaining(self) -> int:
        """Get number of bytes remaining."""
        return self.length - self.tell()

    def read_bytes(self, count: int) -> bytes:
        """Read raw bytes."""
        data = self.stream.read(count)
        if len(data) != count:
            raise ValueError(f"Expected {count} bytes, got {len(data)}")
        return data

    def read_byte(self) -> int:
        """Read unsigned 8-bit integer."""
        return struct.unpack("<B", self.read_bytes(1))[0]

    def read_int16(self) -> int:
        """Read signed 16-bit integer."""
        return struct.unpack("<h", self.read_bytes(2))[0]

    def read_uint16(self) -> int:
        """Read unsigned 16-bit integer."""
        return struct.unpack("<H", self.read_bytes(2))[0]

    def read_int32(self) -> int:
        """Read signed 32-bit integer."""
        return struct.unpack("<i", self.read_bytes(4))[0]

    def read_uint32(self) -> int:
        """Read unsigned 32-bit integer."""
        return struct.unpack("<I", self.read_bytes(4))[0]

    def read_int64(self) -> int:
        """Read signed 64-bit integer."""
        return struct.unpack("<q", self.read_bytes(8))[0]

    def read_uint64(self) -> int:
        """Read unsigned 64-bit integer."""
        return struct.unpack("<Q", self.read_bytes(8))[0]

    def read_float(self) -> float:
        """Read 32-bit float."""
        return struct.unpack("<f", self.read_bytes(4))[0]

    def read_double(self) -> float:
        """Read 64-bit double."""
        return struct.unpack("<d", self.read_bytes(8))[0]

    def read_bool(self) -> bool:
        """Read boolean (16-bit, 0 or 1)."""
        value = self.read_uint16()
        return value != 0

    def read_guid(self) -> str:
        """Read GUID (16 bytes)."""
        guid_bytes = self.read_bytes(16)
        # Parse as UUID
        guid = uuid.UUID(bytes_le=guid_bytes)
        return str(guid)

    def read_filetime(self) -> datetime:
        """
        Read FILETIME (64-bit, 100-nanosecond intervals since 1601-01-01).

        Reference: MS-DTYP Section 2.3.3
        """
        filetime = self.read_uint64()
        if filetime == 0:
            return None
        # Convert from 100-nanosecond intervals to seconds
        # and from 1601-01-01 epoch to Unix epoch
        unix_epoch_filetime = 116444736000000000  # 1970-01-01 in FILETIME
        unix_timestamp = (filetime - unix_epoch_filetime) / 10000000.0
        return datetime.utcfromtimestamp(unix_timestamp)

    def read_string_ascii(self, length: int = None) -> str:
        """
        Read null-terminated ASCII string.

        If length is provided, reads exactly that many bytes.
        Otherwise, reads until null terminator.
        """
        if length is not None:
            data = self.read_bytes(length)
            # Strip null terminator if present
            if data[-1] == 0:
                data = data[:-1]
            return data.decode("latin-1")

        # Read until null terminator
        chars = []
        while True:
            byte = self.read_byte()
            if byte == 0:
                break
            chars.append(byte)
        return bytes(chars).decode("latin-1")

    def read_string_unicode(self, length: int = None) -> str:
        """
        Read null-terminated Unicode (UTF-16LE) string.

        If length is provided, reads exactly that many characters (not bytes!).
        Otherwise, reads until null terminator (0x0000).
        """
        if length is not None:
            # Length is in characters, not bytes
            data = self.read_bytes(length * 2)
            # Strip null terminator if present
            if data[-2:] == b"\x00\x00":
                data = data[:-2]
            return data.decode("utf-16-le")

        # Read until null terminator (0x0000)
        chars = []
        while True:
            char_bytes = self.read_bytes(2)
            if char_bytes == b"\x00\x00":
                break
            chars.append(char_bytes)
        return b"".join(chars).decode("utf-16-le")

    def read_binary(self, length: int) -> bytes:
        """Read binary data of specified length."""
        return self.read_bytes(length)


class BinaryWriter:
    """
    Binary writer for MAPI data structures.

    All writes are little-endian unless otherwise specified.
    """

    def __init__(self):
        self.stream = io.BytesIO()

    def tell(self) -> int:
        """Get current position in stream."""
        return self.stream.tell()

    def get_bytes(self) -> bytes:
        """Get all written bytes."""
        return self.stream.getvalue()

    def write_bytes(self, data: bytes):
        """Write raw bytes."""
        self.stream.write(data)

    def write_byte(self, value: int):
        """Write unsigned 8-bit integer."""
        self.stream.write(struct.pack("<B", value))

    def write_int16(self, value: int):
        """Write signed 16-bit integer."""
        self.stream.write(struct.pack("<h", value))

    def write_uint16(self, value: int):
        """Write unsigned 16-bit integer."""
        self.stream.write(struct.pack("<H", value))

    def write_int32(self, value: int):
        """Write signed 32-bit integer."""
        self.stream.write(struct.pack("<i", value))

    def write_uint32(self, value: int):
        """Write unsigned 32-bit integer."""
        self.stream.write(struct.pack("<I", value))

    def write_int64(self, value: int):
        """Write signed 64-bit integer."""
        self.stream.write(struct.pack("<q", value))

    def write_uint64(self, value: int):
        """Write unsigned 64-bit integer."""
        self.stream.write(struct.pack("<Q", value))

    def write_float(self, value: float):
        """Write 32-bit float."""
        self.stream.write(struct.pack("<f", value))

    def write_double(self, value: float):
        """Write 64-bit double."""
        self.stream.write(struct.pack("<d", value))

    def write_bool(self, value: bool):
        """Write boolean (16-bit, 0 or 1)."""
        self.write_uint16(1 if value else 0)

    def write_guid(self, guid_str: str):
        """Write GUID (16 bytes)."""
        guid = uuid.UUID(guid_str)
        self.stream.write(guid.bytes_le)

    def write_filetime(self, dt: datetime):
        """
        Write FILETIME (64-bit, 100-nanosecond intervals since 1601-01-01).

        Reference: MS-DTYP Section 2.3.3
        """
        if dt is None:
            self.write_uint64(0)
            return

        # Convert from Unix timestamp to FILETIME
        unix_epoch_filetime = 116444736000000000  # 1970-01-01 in FILETIME
        unix_timestamp = dt.timestamp()
        filetime = int(unix_timestamp * 10000000) + unix_epoch_filetime
        self.write_uint64(filetime)

    def write_string_ascii(self, value: str, null_terminate: bool = True):
        """Write ASCII string (Latin-1 encoding)."""
        data = value.encode("latin-1")
        self.stream.write(data)
        if null_terminate:
            self.write_byte(0)

    def write_string_unicode(self, value: str, null_terminate: bool = True):
        """Write Unicode string (UTF-16LE encoding)."""
        data = value.encode("utf-16-le")
        self.stream.write(data)
        if null_terminate:
            self.stream.write(b"\x00\x00")

    def write_binary(self, data: bytes):
        """Write binary data."""
        self.stream.write(data)


class PropertyValue:
    """
    Represents a MAPI property value.

    Reference: MS-OXCDATA Section 2.11.1 (Property Data Types)
    """

    def __init__(self, prop_tag: int, value: Any):
        self.prop_tag = prop_tag
        self.prop_type = prop_tag & 0xFFFF
        self.prop_id = (prop_tag >> 16) & 0xFFFF
        self.value = value

    def encode(self) -> bytes:
        """Encode property value to binary."""
        writer = BinaryWriter()
        writer.write_uint32(self.prop_tag)

        # Encode value based on type
        if self.prop_type == PT_NULL:
            pass  # No value

        elif self.prop_type == PT_I2:
            writer.write_int16(self.value)

        elif self.prop_type == PT_LONG:
            writer.write_int32(self.value)

        elif self.prop_type == PT_I8:
            writer.write_int64(self.value)

        elif self.prop_type == PT_BOOLEAN:
            writer.write_bool(self.value)

        elif self.prop_type == PT_STRING8:
            # Write length-prefixed string
            str_bytes = self.value.encode("latin-1")
            writer.write_uint32(len(str_bytes) + 1)  # +1 for null terminator
            writer.write_bytes(str_bytes)
            writer.write_byte(0)  # Null terminator

        elif self.prop_type == PT_UNICODE:
            # Write length-prefixed Unicode string
            str_bytes = self.value.encode("utf-16-le")
            writer.write_uint32(len(str_bytes) + 2)  # +2 for null terminator
            writer.write_bytes(str_bytes)
            writer.write_bytes(b"\x00\x00")  # Null terminator

        elif self.prop_type == PT_SYSTIME:
            writer.write_filetime(self.value)

        elif self.prop_type == PT_BINARY:
            # Write length-prefixed binary data
            writer.write_uint32(len(self.value))
            writer.write_bytes(self.value)

        elif self.prop_type == PT_CLSID:
            writer.write_guid(self.value)

        elif self.prop_type in (PT_MV_UNICODE, PT_MV_STRING8):
            # Multi-value string
            writer.write_uint32(len(self.value))  # Count
            for s in self.value:
                if self.prop_type == PT_MV_UNICODE:
                    str_bytes = s.encode("utf-16-le")
                else:
                    str_bytes = s.encode("latin-1")
                writer.write_uint32(
                    len(str_bytes) + (2 if self.prop_type == PT_MV_UNICODE else 1)
                )
                writer.write_bytes(str_bytes)
                writer.write_bytes(
                    b"\x00\x00" if self.prop_type == PT_MV_UNICODE else b"\x00"
                )

        else:
            raise NotImplementedError(
                f"Property type 0x{self.prop_type:04X} not implemented"
            )

        return writer.get_bytes()

    @staticmethod
    def decode(reader: BinaryReader) -> "PropertyValue":
        """Decode property value from binary."""
        prop_tag = reader.read_uint32()
        prop_type = prop_tag & 0xFFFF

        # Decode value based on type
        if prop_type == PT_NULL:
            value = None

        elif prop_type == PT_I2:
            value = reader.read_int16()

        elif prop_type == PT_LONG:
            value = reader.read_int32()

        elif prop_type == PT_I8:
            value = reader.read_int64()

        elif prop_type == PT_BOOLEAN:
            value = reader.read_bool()

        elif prop_type == PT_STRING8:
            length = reader.read_uint32()
            value = reader.read_string_ascii(length - 1)  # -1 for null terminator
            reader.read_byte()  # Skip null terminator

        elif prop_type == PT_UNICODE:
            length = reader.read_uint32()
            char_count = (length - 2) // 2  # -2 for null terminator, /2 for UTF-16
            value = reader.read_string_unicode(char_count)
            reader.read_bytes(2)  # Skip null terminator

        elif prop_type == PT_SYSTIME:
            value = reader.read_filetime()

        elif prop_type == PT_BINARY:
            length = reader.read_uint32()
            value = reader.read_binary(length)

        elif prop_type == PT_CLSID:
            value = reader.read_guid()

        elif prop_type in (PT_MV_UNICODE, PT_MV_STRING8):
            count = reader.read_uint32()
            value = []
            for _ in range(count):
                length = reader.read_uint32()
                if prop_type == PT_MV_UNICODE:
                    char_count = (length - 2) // 2
                    s = reader.read_string_unicode(char_count)
                    reader.read_bytes(2)  # Skip null terminator
                else:
                    s = reader.read_string_ascii(length - 1)
                    reader.read_byte()  # Skip null terminator
                value.append(s)

        else:
            raise NotImplementedError(
                f"Property type 0x{prop_type:04X} not implemented"
            )

        return PropertyValue(prop_tag, value)


def encode_property_row(properties: List[PropertyValue]) -> bytes:
    """
    Encode a property row (multiple properties).

    Reference: MS-OXCDATA Section 2.8.1 (Property Row Structures)
    """
    writer = BinaryWriter()
    writer.write_uint16(len(properties))  # Property count

    for prop in properties:
        writer.write_bytes(prop.encode())

    return writer.get_bytes()


def decode_property_row(reader: BinaryReader) -> List[PropertyValue]:
    """
    Decode a property row (multiple properties).

    Reference: MS-OXCDATA Section 2.8.1 (Property Row Structures)
    """
    prop_count = reader.read_uint16()
    properties = []

    for _ in range(prop_count):
        prop = PropertyValue.decode(reader)
        properties.append(prop)

    return properties
