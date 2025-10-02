"""
WBXML Parser for ActiveSync requests
Parses WBXML request bodies to extract SyncKey and other parameters
"""

def parse_wbxml_sync_request(wbxml_bytes: bytes) -> dict:
    """
    Parse WBXML Sync request to extract SyncKey, WindowSize, and other parameters
    Returns a dictionary with parsed values: sync_key, collection_id, window_size
    """
    if not wbxml_bytes or len(wbxml_bytes) < 6:
        return {"sync_key": "0", "collection_id": "1", "window_size": "5"}
    
    # Check for WBXML header (0x03 0x01)
    if not wbxml_bytes.startswith(b'\x03\x01'):
        return {"sync_key": "0", "collection_id": "1", "window_size": "5"}
    
    try:
        # WBXML structure for Sync request:
        # 0x03 0x01 - WBXML header
        # 0x6A - AirSync codepage switch
        # 0x00 0x00 0x07 - String table length
        # 0x56 - Version
        # 0x45 - Sync start tag
        # 0x52 - SyncKey tag (0x20 + 0x40 content flag)
        # 0x03 - STR_I
        # [sync_key_value] - The actual sync key
        # 0x00 - String terminator
        # 0x01 - END tag
        
        sync_key = "0"
        collection_id = "1"
        window_size = "5"  # Default to 5 emails per sync
        
        # Look for WindowSize pattern: 0x52 0x03 [value] 0x00 0x01
        # WindowSize token is 0x52 (0x12 + 0x40 content flag) in AirSync codepage
        pos = 0
        while pos < len(wbxml_bytes) - 4:
            if (wbxml_bytes[pos] == 0x52 and  # WindowSize tag
                pos + 1 < len(wbxml_bytes) and wbxml_bytes[pos + 1] == 0x03):  # STR_I
                
                # Find the string terminator (0x00)
                str_start = pos + 2
                str_end = str_start
                while str_end < len(wbxml_bytes) and wbxml_bytes[str_end] != 0x00:
                    str_end += 1
                
                if str_end < len(wbxml_bytes):
                    # Extract the window size value
                    window_size_bytes = wbxml_bytes[str_start:str_end]
                    try:
                        window_size = window_size_bytes.decode('utf-8', errors='ignore')
                    except:
                        window_size = "5"
                    break
            
            pos += 1
        
        # Look for SyncKey pattern: 0x4B 0x03 [value] 0x00 0x01
        # SyncKey token is 0x4B (0x0B + 0x40 content flag)
        pos = 0
        while pos < len(wbxml_bytes) - 4:
            if (wbxml_bytes[pos] == 0x4B and  # SyncKey tag
                pos + 1 < len(wbxml_bytes) and wbxml_bytes[pos + 1] == 0x03):  # STR_I
                
                # Find the string terminator (0x00)
                str_start = pos + 2
                str_end = str_start
                while str_end < len(wbxml_bytes) and wbxml_bytes[str_end] != 0x00:
                    str_end += 1
                
                if str_end < len(wbxml_bytes):
                    # Extract the sync key value
                    sync_key_bytes = wbxml_bytes[str_start:str_end]
                    sync_key = sync_key_bytes.decode('utf-8', errors='ignore')
                    break
            
            pos += 1
        
        # Look for CollectionId pattern: 0x51 0x03 [value] 0x00 0x01
        # CollectionId token is 0x51 (0x11 + 0x40 content flag)
        pos = 0
        while pos < len(wbxml_bytes) - 4:
            if (wbxml_bytes[pos] == 0x51 and  # CollectionId tag
                pos + 1 < len(wbxml_bytes) and wbxml_bytes[pos + 1] == 0x03):  # STR_I
                
                # Find the string terminator (0x00)
                str_start = pos + 2
                str_end = str_start
                while str_end < len(wbxml_bytes) and wbxml_bytes[str_end] != 0x00:
                    str_end += 1
                
                if str_end < len(wbxml_bytes):
                    # Extract the collection id value
                    collection_id_bytes = wbxml_bytes[str_start:str_end]
                    collection_id = collection_id_bytes.decode('utf-8', errors='ignore')
                    break
            
            pos += 1
        
        return {
            "sync_key": sync_key,
            "collection_id": collection_id,
            "window_size": window_size
        }
        
    except Exception as e:
        # If parsing fails, return defaults
        return {"sync_key": "0", "collection_id": "1", "window_size": "5"}


def parse_wbxml_foldersync_request(wbxml_bytes: bytes) -> dict:
    """
    Parse WBXML FolderSync request to extract SyncKey
    """
    if not wbxml_bytes or len(wbxml_bytes) < 6:
        return {"sync_key": "0"}
    
    # Check for WBXML header (0x03 0x01)
    if not wbxml_bytes.startswith(b'\x03\x01'):
        return {"sync_key": "0"}
    
    try:
        sync_key = "0"
        
        # Look for SyncKey pattern: 0x52 0x03 [value] 0x00 0x01
        pos = 0
        while pos < len(wbxml_bytes) - 4:
            if (wbxml_bytes[pos] == 0x52 and  # SyncKey tag
                pos + 1 < len(wbxml_bytes) and wbxml_bytes[pos + 1] == 0x03):  # STR_I
                
                # Find the string terminator (0x00)
                str_start = pos + 2
                str_end = str_start
                while str_end < len(wbxml_bytes) and wbxml_bytes[str_end] != 0x00:
                    str_end += 1
                
                if str_end < len(wbxml_bytes):
                    # Extract the sync key value
                    sync_key_bytes = wbxml_bytes[str_start:str_end]
                    sync_key = sync_key_bytes.decode('utf-8', errors='ignore')
                    break
            
            pos += 1
        
        return {"sync_key": sync_key}
        
    except Exception as e:
        # If parsing fails, return defaults
        return {"sync_key": "0"}
