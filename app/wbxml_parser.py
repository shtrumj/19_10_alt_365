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


def parse_wbxml_sync_fetch_and_delete(wbxml_bytes: bytes) -> dict:
    """
    Very small WBXML scanner to extract AirSync Fetch and Delete ServerIds from a Sync request.
    Returns: { 'fetch_ids': [server_id,...], 'delete_ids': [server_id,...] }
    Notes: This is a best-effort parser; it looks for AirSync codepage and
    detects tokens: Fetch (0x0A|content -> 0x4A), Delete (0x09|content -> 0x49),
    and ServerId (0x0D|content -> 0x4D), then reads STR_I text.
    """
    fetch_ids = []
    delete_ids = []
    if not wbxml_bytes:
        return {"fetch_ids": fetch_ids, "delete_ids": delete_ids}
    SWITCH_PAGE = 0x00
    END = 0x01
    STR_I = 0x03
    CP_AIRSYNC = 0
    AS_Fetch = 0x0A
    AS_Delete = 0x09
    AS_ServerId = 0x0D

    cp = None
    i = 0
    in_fetch = False
    in_delete = False

    def read_cstr(buf, pos):
        j = pos
        while j < len(buf) and buf[j] != 0x00:
            j += 1
        s = buf[pos:j].decode('utf-8', errors='ignore')
        return s, j + 1

    while i < len(wbxml_bytes):
        b = wbxml_bytes[i]
        i += 1
        if b == SWITCH_PAGE:
            if i >= len(wbxml_bytes):
                break
            cp = wbxml_bytes[i]
            i += 1
            continue
        if b == END:
            # closing a tag; reset context if leaving fetch/delete
            if in_fetch:
                in_fetch = False
            if in_delete:
                in_delete = False
            continue
        tok = b & 0x3F  # strip content bit
        has_content = (b & 0x40) != 0
        if cp == CP_AIRSYNC:
            if tok == AS_Fetch and has_content:
                in_fetch = True; in_delete = False
                continue
            if tok == AS_Delete and has_content:
                in_delete = True; in_fetch = False
                continue
            if tok == AS_ServerId and has_content:
                # Next significant token should be STR_I then the string
                while i < len(wbxml_bytes) and wbxml_bytes[i] != STR_I:
                    i += 1
                if i < len(wbxml_bytes) and wbxml_bytes[i] == STR_I:
                    i += 1
                    sid, i = read_cstr(wbxml_bytes, i)
                    if in_fetch and sid:
                        fetch_ids.append(sid)
                    elif in_delete and sid:
                        delete_ids.append(sid)
                continue
    return {"fetch_ids": fetch_ids, "delete_ids": delete_ids}
    
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
