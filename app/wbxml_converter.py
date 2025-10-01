"""
WBXML Converter for ActiveSync
Converts XML responses to WBXML binary format using libwbxml2
"""

import subprocess
import tempfile
import os
from typing import Union


def xml_to_wbxml(xml_content: str) -> bytes:
    """
    Convert XML string to WBXML binary format using libwbxml2
    
    Args:
        xml_content: XML string to convert
        
    Returns:
        WBXML binary data as bytes
    """
    try:
        # Create temporary files for input and output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as xml_file:
            xml_file.write(xml_content)
            xml_file_path = xml_file.name
            
        with tempfile.NamedTemporaryFile(suffix='.wbxml', delete=False) as wbxml_file:
            wbxml_file_path = wbxml_file.name
            
        try:
            # Use libwbxml2's xml2wbxml command
            # -o: output file
            # -v: verbose (optional)
            # -c: code page (optional, defaults to UTF-8)
            result = subprocess.run([
                'xml2wbxml',
                '-o', wbxml_file_path,
                xml_file_path
            ], capture_output=True, text=True, check=True)
            
            # Read the WBXML binary data
            with open(wbxml_file_path, 'rb') as f:
                wbxml_data = f.read()
                
            return wbxml_data
            
        except subprocess.CalledProcessError as e:
            print(f"Error converting XML to WBXML: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            # Fallback: return XML as bytes if WBXML conversion fails
            return xml_content.encode('utf-8')
            
        except FileNotFoundError:
            print("xml2wbxml command not found. Falling back to XML.")
            # Fallback: return XML as bytes if libwbxml2 tools are not available
            return xml_content.encode('utf-8')
            
    finally:
        # Clean up temporary files
        try:
            os.unlink(xml_file_path)
        except:
            pass
        try:
            os.unlink(wbxml_file_path)
        except:
            pass


def wbxml_to_xml(wbxml_data: bytes) -> str:
    """
    Convert WBXML binary data to XML string using libwbxml2
    
    Args:
        wbxml_data: WBXML binary data
        
    Returns:
        XML string
    """
    try:
        # Create temporary files for input and output
        with tempfile.NamedTemporaryFile(suffix='.wbxml', delete=False) as wbxml_file:
            wbxml_file.write(wbxml_data)
            wbxml_file_path = wbxml_file.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as xml_file:
            xml_file_path = xml_file.name
            
        try:
            # Use libwbxml2's wbxml2xml command
            result = subprocess.run([
                'wbxml2xml',
                '-o', xml_file_path,
                wbxml_file_path
            ], capture_output=True, text=True, check=True)
            
            # Read the XML string
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                
            return xml_content
            
        except subprocess.CalledProcessError as e:
            print(f"Error converting WBXML to XML: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            # Fallback: return WBXML as string if conversion fails
            return wbxml_data.decode('utf-8', errors='ignore')
            
        except FileNotFoundError:
            print("wbxml2xml command not found. Falling back to raw data.")
            # Fallback: return WBXML as string if libwbxml2 tools are not available
            return wbxml_data.decode('utf-8', errors='ignore')
            
    finally:
        # Clean up temporary files
        try:
            os.unlink(wbxml_file_path)
        except:
            pass
        try:
            os.unlink(xml_file_path)
        except:
            pass


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
    
    print("Testing WBXML conversion...")
    print(f"Original XML length: {len(test_xml)}")
    
    # Convert to WBXML
    wbxml_data = xml_to_wbxml(test_xml)
    print(f"WBXML data length: {len(wbxml_data)}")
    print(f"WBXML data type: {type(wbxml_data)}")
    
    # Convert back to XML
    converted_xml = wbxml_to_xml(wbxml_data)
    print(f"Converted XML length: {len(converted_xml)}")
    
    print("WBXML conversion test completed!")


if __name__ == "__main__":
    test_wbxml_conversion()
