"""
WBXML Encoder based on grommunio-sync implementation
Implements delayed output mechanism and stack-based tag management
"""

import io
from typing import Dict, List, Optional, Union


class WBXMLEncoderGrommunio:
    """
    WBXML Encoder implementing grommunio-sync delayed output mechanism
    Based on the grommunio-sync WBXMLEncoder.php implementation
    """
    
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
    
    def __init__(self, output_stream: io.BytesIO, multipart: bool = False):
        self._out = output_stream
        self._multipart = multipart
        self._current_cp = 0
        self._stack = []  # Delayed output stack
        self._bodyparts = []  # For multipart support
        self._log = False  # Debug logging
        self._log_stack = []  # For debug logging
        
        # DTD mapping (simplified version of grommunio-sync)
        self._dtd = {
            "namespaces": {
                "FolderHierarchy": 1,
                "AirSync": 0,
                "Provision": 2,
                "Settings": 3,
                "Search": 4,
                "ItemOperations": 5,
                "ResolveRecipients": 6,
                "ValidateCert": 7,
            },
            "codes": {
                0: {  # AirSync codepage
                    "Sync": 0x05,
                    "Collections": 0x06,
                    "Collection": 0x07,
                    "CollectionId": 0x08,
                    "Status": 0x09,
                    "SyncKey": 0x0A,
                    "Commands": 0x0B,
                    "Add": 0x0C,
                    "Delete": 0x0D,
                    "Change": 0x0E,
                    "ServerId": 0x0F,
                    "ApplicationData": 0x10,
                    "Subject": 0x11,
                    "From": 0x12,
                    "To": 0x13,
                    "DateReceived": 0x14,
                    "DisplayTo": 0x15,
                    "ThreadTopic": 0x16,
                    "Importance": 0x17,
                    "Read": 0x18,
                    "Body": 0x19,
                    "MessageClass": 0x1A,
                    "InternetCPID": 0x1B,
                    "ContentClass": 0x1C,
                    "NativeBodyType": 0x1D,
                    "ConversationId": 0x1E,
                    "ConversationIndex": 0x1F,
                    "Categories": 0x20,
                },
                1: {  # FolderHierarchy codepage
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
        
        # Reverse mapping for lookups
        self._dtd_reverse = {}
        for ns_id, ns_name in self._dtd["namespaces"].items():
            self._dtd_reverse[ns_name] = ns_id
        
        for cp, codes in self._dtd["codes"].items():
            self._dtd_reverse[cp] = {}
            for code, tag in codes.items():
                self._dtd_reverse[cp][tag] = code
    
    def start_wbxml(self):
        """Write WBXML header - grommunio-sync style"""
        if self._multipart:
            # Set multipart content type
            pass  # Would set header in real implementation
        
        # WBXML version 1.3
        self._out.write(b'\x03')
        # Public ID 1 (ActiveSync)
        self._out.write(b'\x01')
        # UTF-8 charset
        self._out.write(b'\x6a')
        # String table length (0)
        self._out.write(b'\x00')
    
    def start_tag(self, tag: str, attributes: Optional[Dict] = None, no_content: bool = False):
        """
        Start a WBXML tag with delayed output mechanism
        Based on grommunio-sync implementation
        """
        if not no_content:
            # Add to delayed output stack
            stack_elem = {
                'tag': tag,
                'sent': False,
                'nocontent': no_content
            }
            self._stack.append(stack_elem)
            
            if self._log:
                self._log_start_tag(tag, no_content)
        else:
            # Force immediate output for no-content tags
            self._output_stack()
            self._start_tag(tag, no_content)
    
    def end_tag(self):
        """End a WBXML tag - grommunio-sync style"""
        if not self._stack:
            return
        
        stack_elem = self._stack.pop()
        
        # Only output end tags for items that had a start tag sent
        if stack_elem['sent']:
            self._end_tag()
            
            if self._log:
                self._log_end_tag()
            
            # Handle multipart completion
            if len(self._stack) == 0 and self._multipart:
                self._process_multipart()
    
    def content(self, content: str):
        """
        Add content with grommunio-sync filtering
        """
        if not content:
            return
        
        # Filter out null characters (grommunio-sync does this)
        content = content.replace('\x00', '')
        if not content:
            return
        
        # Output any pending tags
        self._output_stack()
        self._content(content)
        
        if self._log:
            self._log_content(content)
    
    def _output_stack(self):
        """
        Output any tags on the stack that haven't been output yet
        This is the core of the delayed output mechanism
        """
        for stack_elem in self._stack:
            if not stack_elem['sent']:
                self._start_tag(stack_elem['tag'], stack_elem['nocontent'])
                stack_elem['sent'] = True
    
    def _start_tag(self, tag: str, no_content: bool = False):
        """Output actual start tag with proper codepage handling"""
        mapping = self._get_mapping(tag)
        if not mapping:
            return False
        
        # Switch codepage if needed
        if self._current_cp != mapping["cp"]:
            self._out.write(b'\x00')  # SWITCH_PAGE
            self._out.write(bytes([mapping["cp"]]))
            self._current_cp = mapping["cp"]
        
        code = mapping["code"]
        
        # Set content flag if not no-content
        if not no_content:
            code |= 0x40
        
        self._out.write(bytes([code]))
    
    def _end_tag(self):
        """Output end tag"""
        self._out.write(b'\x01')  # END
    
    def _content(self, content: str):
        """Output content with proper encoding"""
        self._out.write(b'\x03')  # STR_I
        self._out.write(content.encode('utf-8'))
        self._out.write(b'\x00')  # String terminator
    
    def _get_mapping(self, tag: str):
        """Get codepage and code for a tag"""
        # Parse namespace:tag format
        if ':' in tag:
            namespace, tag_name = tag.split(':', 1)
        else:
            namespace = "AirSync"  # Default
            tag_name = tag
        
        # Get codepage
        if namespace in self._dtd["namespaces"]:
            cp = self._dtd["namespaces"][namespace]
        else:
            cp = 0  # Default to AirSync
        
        # Get code
        if cp in self._dtd["codes"] and tag_name in self._dtd["codes"][cp]:
            code = self._dtd["codes"][cp][tag_name]
        else:
            return None
        
        return {"cp": cp, "code": code}
    
    def _process_multipart(self):
        """Process multipart response (grommunio-sync feature)"""
        # This would handle multipart responses in a real implementation
        pass
    
    def _log_start_tag(self, tag: str, no_content: bool):
        """Debug logging for start tags"""
        spaces = " " * len(self._log_stack)
        if no_content:
            print(f"O {spaces} <{tag}/>")
        else:
            self._log_stack.append(tag)
            print(f"O {spaces} <{tag}>")
    
    def _log_end_tag(self):
        """Debug logging for end tags"""
        if self._log_stack:
            spaces = " " * (len(self._log_stack) - 1)
            tag = self._log_stack.pop()
            print(f"O {spaces} </{tag}>")
    
    def _log_content(self, content: str):
        """Debug logging for content"""
        spaces = " " * len(self._log_stack)
        print(f"O {spaces} {content}")


def create_foldersync_wbxml_grommunio(sync_key: str = "1", count: int = 7) -> bytes:
    """
    Create FolderSync WBXML response using grommunio-sync approach
    """
    output = io.BytesIO()
    encoder = WBXMLEncoderGrommunio(output)
    
    # Start WBXML
    encoder.start_wbxml()
    
    # FolderSync with delayed output
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
    
    # Add folders with delayed output
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
        # Add folder
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


def test_grommunio_wbxml():
    """Test the grommunio-style WBXML encoder"""
    print("Testing Grommunio-Style WBXML Encoder...")
    
    # Test FolderSync
    foldersync_wbxml = create_foldersync_wbxml_grommunio()
    print(f"FolderSync WBXML length: {len(foldersync_wbxml)}")
    print(f"FolderSync WBXML (first 20 bytes): {foldersync_wbxml[:20].hex()}")
    
    # Compare with our previous implementations
    from app.wbxml_encoder import create_foldersync_wbxml as v1
    from app.wbxml_encoder_v2 import create_foldersync_wbxml_v2 as v2
    
    v1_wbxml = v1()
    v2_wbxml = v2()
    
    print(f"V1 Length: {len(v1_wbxml)}")
    print(f"V2 Length: {len(v2_wbxml)}")
    print(f"Grommunio Length: {len(foldersync_wbxml)}")
    print(f"V1 == Grommunio: {v1_wbxml == foldersync_wbxml}")
    print(f"V2 == Grommunio: {v2_wbxml == foldersync_wbxml}")
    
    print("Grommunio-Style WBXML Encoder test completed!")


if __name__ == "__main__":
    test_grommunio_wbxml()
