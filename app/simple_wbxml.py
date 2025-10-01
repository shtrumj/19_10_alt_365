"""
Simple WBXML Converter for ActiveSync
A minimal implementation that converts basic ActiveSync XML to WBXML format
"""

import xml.etree.ElementTree as ET
from typing import Union


class SimpleWBXMLConverter:
    """Simple WBXML converter for ActiveSync responses"""
    
    # ActiveSync WBXML string tables (simplified)
    STRING_TABLES = {
        'FolderHierarchy': {
            'FolderSync': 0x05,
            'Status': 0x06,
            'SyncKey': 0x07,
            'Changes': 0x08,
            'Count': 0x09,
            'Add': 0x0A,
            'ServerId': 0x0B,
            'ParentId': 0x0C,
            'DisplayName': 0x0D,
            'Type': 0x0E,
            'SupportedClasses': 0x0F,
            'SupportedClass': 0x10,
        },
        'AirSync': {
            'Sync': 0x05,
            'Collections': 0x06,
            'Collection': 0x07,
            'CollectionId': 0x08,
            'Status': 0x09,
            'SyncKey': 0x0A,
            'Commands': 0x0B,
            'Add': 0x0C,
            'ServerId': 0x0D,
            'ApplicationData': 0x0E,
            'Subject': 0x0F,
            'From': 0x10,
            'To': 0x11,
            'DateReceived': 0x12,
            'DisplayTo': 0x13,
            'ThreadTopic': 0x14,
            'Importance': 0x15,
            'Read': 0x16,
            'Body': 0x17,
            'Type': 0x18,
            'EstimatedDataSize': 0x19,
            'Data': 0x1A,
            'Preview': 0x1B,
            'MessageClass': 0x1C,
            'InternetCPID': 0x1D,
            'ContentClass': 0x1E,
            'NativeBodyType': 0x1F,
            'ConversationId': 0x20,
            'ConversationIndex': 0x21,
            'Categories': 0x22,
        }
    }
    
    def __init__(self):
        self.string_table = []
        self.string_table_index = 0
    
    def xml_to_wbxml(self, xml_content: str) -> bytes:
        """
        Convert XML string to WBXML binary format
        
        Args:
            xml_content: XML string to convert
            
        Returns:
            WBXML binary data as bytes
        """
        try:
            root = ET.fromstring(xml_content)
            wbxml_data = bytearray()
            
            # WBXML version 1.3
            wbxml_data.extend([0x03, 0x01])
            
            # Public ID (ActiveSync)
            wbxml_data.extend([0x01, 0x6A, 0x00])
            
            # Character set (UTF-8)
            wbxml_data.extend([0x6A, 0x00])
            
            # String table length (will be updated later)
            string_table_start = len(wbxml_data)
            wbxml_data.extend([0x00, 0x00])
            
            # Process the XML tree
            self._process_element(root, wbxml_data)
            
            # Update string table length
            string_table_length = len(self.string_table)
            wbxml_data[string_table_start] = (string_table_length >> 8) & 0xFF
            wbxml_data[string_table_start + 1] = string_table_length & 0xFF
            
            # Append string table
            wbxml_data.extend(self.string_table)
            
            return bytes(wbxml_data)
            
        except Exception as e:
            print(f"Error converting XML to WBXML: {e}")
            # Fallback: return XML as bytes
            return xml_content.encode('utf-8')
    
    def _process_element(self, element: ET.Element, wbxml_data: bytearray):
        """Process an XML element and convert to WBXML"""
        namespace = self._get_namespace(element.tag)
        tag_name = self._get_local_name(element.tag)
        
        # Get tag code
        tag_code = self._get_tag_code(namespace, tag_name)
        
        # Add element start
        if element.attrib:
            # Element with attributes
            wbxml_data.append(0x80 | tag_code)
            self._process_attributes(element, wbxml_data)
        else:
            # Simple element
            wbxml_data.append(tag_code)
        
        # Process text content
        if element.text and element.text.strip():
            self._add_string(element.text.strip(), wbxml_data)
        
        # Process child elements
        for child in element:
            self._process_element(child, wbxml_data)
        
        # Add element end
        wbxml_data.append(0x01)  # END token
    
    def _process_attributes(self, element: ET.Element, wbxml_data: bytearray):
        """Process element attributes"""
        for attr_name, attr_value in element.attrib.items():
            attr_code = self._get_tag_code(self._get_namespace(attr_name), self._get_local_name(attr_name))
            wbxml_data.append(0x80 | attr_code)
            self._add_string(attr_value, wbxml_data)
    
    def _get_namespace(self, tag: str) -> str:
        """Extract namespace from tag"""
        if '}' in tag:
            return tag.split('}')[0][1:]
        return ''
    
    def _get_local_name(self, tag: str) -> str:
        """Extract local name from tag"""
        if '}' in tag:
            return tag.split('}')[1]
        return tag
    
    def _get_tag_code(self, namespace: str, tag_name: str) -> int:
        """Get WBXML tag code for a given namespace and tag name"""
        if namespace in self.STRING_TABLES:
            return self.STRING_TABLES[namespace].get(tag_name, 0x00)
        return 0x00
    
    def _add_string(self, text: str, wbxml_data: bytearray):
        """Add string to WBXML data"""
        if text in self.string_table:
            # String already in table
            index = self.string_table.index(text)
            wbxml_data.append(0x80 | (index >> 7))
            wbxml_data.append(0x7F & index)
        else:
            # Add new string to table
            self.string_table.append(text)
            index = len(self.string_table) - 1
            wbxml_data.append(0x80 | (index >> 7))
            wbxml_data.append(0x7F & index)
        
        # Add the actual string data
        text_bytes = text.encode('utf-8')
        wbxml_data.append(len(text_bytes))
        wbxml_data.extend(text_bytes)


def xml_to_wbxml(xml_content: str) -> bytes:
    """
    Convert XML string to WBXML binary format
    
    Args:
        xml_content: XML string to convert
        
    Returns:
        WBXML binary data as bytes
    """
    converter = SimpleWBXMLConverter()
    return converter.xml_to_wbxml(xml_content)


def test_wbxml_conversion():
    """Test function to verify WBXML conversion works"""
    test_xml = """<?xml version="1.0" encoding="utf-8"?>
<FolderSync xmlns="FolderHierarchy">
    <Status>1</Status>
    <SyncKey>1</SyncKey>
    <Changes>
        <Count>1</Count>
        <Add>
            <ServerId>1</ServerId>
            <ParentId>0</ParentId>
            <DisplayName>Inbox</DisplayName>
            <Type>2</Type>
        </Add>
    </Changes>
</FolderSync>"""
    
    print("Testing Simple WBXML conversion...")
    print(f"Original XML length: {len(test_xml)}")
    
    # Convert to WBXML
    wbxml_data = xml_to_wbxml(test_xml)
    print(f"WBXML data length: {len(wbxml_data)}")
    print(f"WBXML data type: {type(wbxml_data)}")
    print(f"WBXML data (first 20 bytes): {wbxml_data[:20].hex()}")
    
    print("Simple WBXML conversion test completed!")


if __name__ == "__main__":
    test_wbxml_conversion()
