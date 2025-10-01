"""
WBXML Encoder for ActiveSync
Based on grommunio-sync implementation: https://github.com/grommunio/grommunio-sync
Implements WBXML 1.3 specification for Exchange ActiveSync
"""

import io
from typing import Dict, List, Optional, Union


class WBXMLEncoder:
    """WBXML Encoder following the WBXML 1.3 specification"""
    
    # WBXML constants
    WBXML_END = 0x01
    WBXML_ENTITY = 0x02
    WBXML_STR_I = 0x03
    WBXML_LITERAL = 0x04
    WBXML_EXT_I_0 = 0x40
    WBXML_EXT_I_1 = 0x41
    WBXML_EXT_I_2 = 0x42
    WBXML_PI = 0x43
    WBXML_LITERAL_C = 0x44
    WBXML_EXT_T_0 = 0x80
    WBXML_EXT_T_1 = 0x81
    WBXML_EXT_T_2 = 0x82
    WBXML_STR_T = 0x83
    WBXML_LITERAL_A = 0x84
    WBXML_EXT_0 = 0xC0
    WBXML_EXT_1 = 0xC1
    WBXML_EXT_2 = 0xC2
    WBXML_OPAQUE = 0xC3
    WBXML_LITERAL_AC = 0xC4
    WBXML_SWITCH_PAGE = 0x00
    
    # ActiveSync WBXML DTD definitions
    DTD = {
        "namespaces": {
            "AirSync": 0,
            "FolderHierarchy": 1,
            "Provision": 2,
            "Settings": 3,
            "Search": 4,
            "ItemOperations": 5,
            "ResolveRecipients": 6,
            "ValidateCert": 7,
            "ComposeMail": 8,
            "Move": 9,
            "MeetingResponse": 10,
            "GetItemEstimate": 11,
            "Ping": 12,
            "Calendar": 13,
        },
        "codes": {
            0: {  # AirSync
                "Sync": 0x05,
                "Collections": 0x06,
                "Collection": 0x07,
                "CollectionId": 0x08,
                "Status": 0x09,
                "SyncKey": 0x0A,
                "Commands": 0x0B,
                "Add": 0x0C,
                "ServerId": 0x0D,
                "ApplicationData": 0x0E,
                "Subject": 0x0F,
                "From": 0x10,
                "To": 0x11,
                "DateReceived": 0x12,
                "DisplayTo": 0x13,
                "ThreadTopic": 0x14,
                "Importance": 0x15,
                "Read": 0x16,
                "Body": 0x17,
                "Type": 0x18,
                "EstimatedDataSize": 0x19,
                "Data": 0x1A,
                "Preview": 0x1B,
                "MessageClass": 0x1C,
                "InternetCPID": 0x1D,
                "ContentClass": 0x1E,
                "NativeBodyType": 0x1F,
                "ConversationId": 0x20,
                "ConversationIndex": 0x21,
                "Categories": 0x22,
            },
            1: {  # FolderHierarchy
                "FolderSync": 0x05,
                "Status": 0x06,
                "SyncKey": 0x07,
                "Changes": 0x08,
                "Count": 0x09,
                "Add": 0x0A,
                "ServerId": 0x0B,
                "ParentId": 0x0C,
                "DisplayName": 0x0D,
                "Type": 0x0E,
                "SupportedClasses": 0x0F,
                "SupportedClass": 0x10,
            }
        }
    }
    
    def __init__(self, output_stream: io.BytesIO):
        self._out = output_stream
        self._current_cp = 0
        self._stack = []
        
    def start_wbxml(self):
        """Write WBXML header"""
        # WBXML version 1.3
        self._out.write(b'\x03')
        # Public ID 1 (ActiveSync)
        self._write_mbuint(0x01)
        # UTF-8 charset
        self._write_mbuint(106)
        # String table length (0 for now)
        self._write_mbuint(0x00)
    
    def start_tag(self, tag: str, attributes: Optional[Dict] = None, no_content: bool = False):
        """Start a WBXML tag"""
        if not no_content:
            self._stack.append({
                'tag': tag,
                'sent': False,
                'no_content': no_content
            })
        else:
            self._output_stack()
            self._start_tag(tag, no_content)
    
    def end_tag(self):
        """End a WBXML tag"""
        if not self._stack:
            return
            
        stack_elem = self._stack.pop()
        if stack_elem['sent']:
            self._end_tag()
    
    def content(self, content: str):
        """Add content to current tag"""
        if not content:
            return
            
        # Filter out null characters
        content = content.replace('\x00', '')
        if not content:
            return
            
        self._output_stack()
        self._content(content)
    
    def _output_stack(self):
        """Output any pending tags on the stack"""
        for stack_elem in self._stack:
            if not stack_elem['sent']:
                self._start_tag(stack_elem['tag'], stack_elem['no_content'])
                stack_elem['sent'] = True
    
    def _start_tag(self, tag: str, no_content: bool = False):
        """Output a start tag"""
        mapping = self._get_mapping(tag)
        if not mapping:
            return False
            
        # Switch codepage if needed
        if self._current_cp != mapping['cp']:
            self._out.write(b'\x00')  # SWITCH_PAGE
            self._out.write(bytes([mapping['cp']]))
            self._current_cp = mapping['cp']
        
        code = mapping['code']
        if not no_content:
            code |= 0x40  # Set content flag
            
        self._out.write(bytes([code]))
    
    def _end_tag(self):
        """Output an end tag"""
        self._out.write(b'\x01')  # END
    
    def _content(self, content: str):
        """Output content"""
        self._out.write(b'\x03')  # STR_I
        self._out.write(content.encode('utf-8'))
        self._out.write(b'\x00')  # String terminator
    
    def _get_mapping(self, tag: str):
        """Get codepage and code for a tag"""
        # Split namespace:tag
        if ':' in tag:
            namespace, tag_name = tag.split(':', 1)
        else:
            namespace = None
            tag_name = tag
        
        # Get codepage
        if namespace and namespace in self.DTD['namespaces']:
            cp = self.DTD['namespaces'][namespace]
        else:
            cp = 0  # Default to AirSync
        
        # Get code
        if cp in self.DTD['codes'] and tag_name in self.DTD['codes'][cp]:
            code = self.DTD['codes'][cp][tag_name]
        else:
            return None
            
        return {'cp': cp, 'code': code}
    
    def _write_mbuint(self, value: int):
        """Write a multi-byte unsigned integer"""
        if value == 0:
            self._out.write(b'\x00')
            return
            
        bytes_list = []
        while value != 0:
            byte = value & 0x7F
            value >>= 7
            if bytes_list:
                byte |= 0x80
            bytes_list.insert(0, byte)
            
        self._out.write(bytes(bytes_list))


def create_foldersync_wbxml(sync_key: str = "1", count: int = 7) -> bytes:
    """Create a WBXML FolderSync response"""
    output = io.BytesIO()
    encoder = WBXMLEncoder(output)
    
    # Start WBXML
    encoder.start_wbxml()
    
    # FolderSync
    encoder.start_tag("FolderHierarchy:FolderSync")
    
    # Status
    encoder.start_tag("FolderHierarchy:Status")
    encoder.content("1")
    encoder.end_tag()
    
    # SyncKey
    encoder.start_tag("FolderHierarchy:SyncKey")
    encoder.content(sync_key)
    encoder.end_tag()
    
    # Changes
    encoder.start_tag("FolderHierarchy:Changes")
    
    # Count
    encoder.start_tag("FolderHierarchy:Count")
    encoder.content(str(count))
    encoder.end_tag()
    
    # FIXED: All 7 folders defined
    folders = [
        ("1", "0", "Inbox", "2", "Email"),
        ("2", "0", "Drafts", "3", "Email"),
        ("3", "0", "Deleted Items", "4", "Email"),
        ("4", "0", "Sent Items", "5", "Email"),
        ("5", "0", "Outbox", "6", "Email"),
        ("calendar", "0", "Calendar", "8", "Calendar"),
        ("contacts", "0", "Contacts", "9", "Contacts")
    ]
    
    # Use only the requested count
    for server_id, parent_id, display_name, folder_type, supported_class in folders[:count]:
        # Add
        encoder.start_tag("FolderHierarchy:Add")
        
        # ServerId
        encoder.start_tag("FolderHierarchy:ServerId")
        encoder.content(server_id)
        encoder.end_tag()
        
        # ParentId
        encoder.start_tag("FolderHierarchy:ParentId")
        encoder.content(parent_id)
        encoder.end_tag()
        
        # DisplayName
        encoder.start_tag("FolderHierarchy:DisplayName")
        encoder.content(display_name)
        encoder.end_tag()
        
        # Type
        encoder.start_tag("FolderHierarchy:Type")
        encoder.content(folder_type)
        encoder.end_tag()
        
        encoder.end_tag()  # End Add
    
    encoder.end_tag()  # End Changes
    encoder.end_tag()  # End FolderSync
    
    return output.getvalue()


def create_sync_wbxml(sync_key: str = "1", emails: List = None) -> bytes:
    """Create a WBXML Sync response"""
    if emails is None:
        emails = []
        
    output = io.BytesIO()
    encoder = WBXMLEncoder(output)
    
    # Start WBXML
    encoder.start_wbxml()
    
    # Sync
    encoder.start_tag("AirSync:Sync")
    
    # Collections
    encoder.start_tag("AirSync:Collections")
    
    # Collection
    encoder.start_tag("AirSync:Collection")
    
    # CollectionId
    encoder.start_tag("AirSync:CollectionId")
    encoder.content("1")
    encoder.end_tag()
    
    # Status
    encoder.start_tag("AirSync:Status")
    encoder.content("1")
    encoder.end_tag()
    
    # SyncKey
    encoder.start_tag("AirSync:SyncKey")
    encoder.content(sync_key)
    encoder.end_tag()
    
    # Commands (empty for now)
    encoder.start_tag("AirSync:Commands")
    encoder.end_tag()
    
    encoder.end_tag()  # End Collection
    encoder.end_tag()  # End Collections
    encoder.end_tag()  # End Sync
    
    return output.getvalue()


def test_wbxml_encoder():
    """Test the WBXML encoder"""
    print("Testing WBXML Encoder...")
    
    # Test FolderSync
    foldersync_wbxml = create_foldersync_wbxml()
    print(f"FolderSync WBXML length: {len(foldersync_wbxml)}")
    print(f"FolderSync WBXML (first 20 bytes): {foldersync_wbxml[:20].hex()}")
    
    # Test Sync
    sync_wbxml = create_sync_wbxml()
    print(f"Sync WBXML length: {len(sync_wbxml)}")
    print(f"Sync WBXML (first 20 bytes): {sync_wbxml[:20].hex()}")
    
    print("WBXML Encoder test completed!")


if __name__ == "__main__":
    test_wbxml_encoder()
