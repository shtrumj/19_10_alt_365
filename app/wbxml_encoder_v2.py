"""
WBXML Encoder V2 for ActiveSync
Based on grommunio-sync implementation with more accurate WBXML structure
"""

import io
from typing import Dict, List, Optional, Union


class WBXMLEncoderV2:
    """WBXML Encoder V2 following grommunio-sync approach"""
    
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
    
    def __init__(self, output_stream: io.BytesIO):
        self._out = output_stream
        self._current_cp = 0
        self._stack = []
        
    def start_wbxml(self):
        """Write WBXML header"""
        # WBXML version 1.3
        self._out.write(b'\x03')
        # Public ID 1 (ActiveSync)
        self._out.write(b'\x01')
        # UTF-8 charset
        self._out.write(b'\x6a')
        # String table length (0 for now)
        self._out.write(b'\x00')
    
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
        # For FolderHierarchy namespace, use codepage 1
        if tag.startswith("FolderHierarchy:"):
            if self._current_cp != 1:
                self._out.write(b'\x00')  # SWITCH_PAGE
                self._out.write(b'\x01')  # Codepage 1
                self._current_cp = 1
            
            # Map tags to codes
            tag_map = {
                "FolderHierarchy:FolderSync": 0x05,
                "FolderHierarchy:Status": 0x06,
                "FolderHierarchy:SyncKey": 0x07,
                "FolderHierarchy:Changes": 0x08,
                "FolderHierarchy:Count": 0x09,
                "FolderHierarchy:Add": 0x0A,
                "FolderHierarchy:ServerId": 0x0B,
                "FolderHierarchy:ParentId": 0x0C,
                "FolderHierarchy:DisplayName": 0x0D,
                "FolderHierarchy:Type": 0x0E,
                "FolderHierarchy:SupportedClasses": 0x0F,
                "FolderHierarchy:SupportedClass": 0x10,
            }
            
            code = tag_map.get(tag, 0x05)
            if not no_content:
                code |= 0x40  # Set content flag
                
            self._out.write(bytes([code]))
        else:
            # For other namespaces, use codepage 0
            if self._current_cp != 0:
                self._out.write(b'\x00')  # SWITCH_PAGE
                self._out.write(b'\x00')  # Codepage 0
                self._current_cp = 0
            
            # Map AirSync tags
            tag_map = {
                "AirSync:Sync": 0x05,
                "AirSync:Collections": 0x06,
                "AirSync:Collection": 0x07,
                "AirSync:CollectionId": 0x08,
                "AirSync:Status": 0x09,
                "AirSync:SyncKey": 0x0A,
                "AirSync:Commands": 0x0B,
            }
            
            code = tag_map.get(tag, 0x05)
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


def create_foldersync_wbxml_v2(sync_key: str = "1", count: int = 7) -> bytes:
    """Create a WBXML FolderSync response using V2 encoder"""
    output = io.BytesIO()
    encoder = WBXMLEncoderV2(output)
    
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
    
    # Add folders
    folders = [
        ("1", "0", "Inbox", "2", "Email"),
        ("2", "0", "Drafts", "3", "Email"),
        ("3", "0", "Deleted Items", "4", "Email"),
        ("4", "0", "Sent Items", "5", "Email"),
        ("5", "0", "Outbox", "6", "Email"),
        ("calendar", "0", "Calendar", "8", "Calendar"),
        ("contacts", "0", "Contacts", "9", "Contacts")
    ]
    
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
        
        # SupportedClasses
        encoder.start_tag("FolderHierarchy:SupportedClasses")
        encoder.start_tag("FolderHierarchy:SupportedClass")
        encoder.content(supported_class)
        encoder.end_tag()
        encoder.end_tag()
        
        encoder.end_tag()  # End Add
    
    encoder.end_tag()  # End Changes
    encoder.end_tag()  # End FolderSync
    
    return output.getvalue()


def test_wbxml_v2():
    """Test the WBXML V2 encoder"""
    print("Testing WBXML Encoder V2...")
    
    # Test FolderSync
    foldersync_wbxml = create_foldersync_wbxml_v2()
    print(f"FolderSync WBXML length: {len(foldersync_wbxml)}")
    print(f"FolderSync WBXML (first 20 bytes): {foldersync_wbxml[:20].hex()}")
    
    print("WBXML Encoder V2 test completed!")


if __name__ == "__main__":
    test_wbxml_v2()
