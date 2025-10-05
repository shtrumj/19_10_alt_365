"""
WBXML Parser for ActiveSync requests
Parses WBXML request bodies to extract SyncKey and other parameters
"""

def parse_wbxml_sync_request(wbxml_bytes: bytes) -> dict:
    """
    Parse WBXML Sync request to extract SyncKey, WindowSize, CollectionId, and
    BodyPreferences (Type/Truncation) requested by the client.
    Returns a dictionary with parsed values.
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
        
        result = {
            "sync_key": sync_key,
            "collection_id": collection_id,
            "window_size": window_size,
        }

        body_prefs = _extract_body_preferences(wbxml_bytes)
        if body_prefs:
            result["body_preferences"] = body_prefs

        return result

    except Exception as e:
        # If parsing fails, return defaults
        return {"sync_key": "0", "collection_id": "1", "window_size": "5"}


def parse_wbxml_foldersync_request(wbxml_bytes: bytes) -> dict:
    """
    Parse WBXML FolderSync request to extract SyncKey
    """
    if not wbxml_bytes or len(wbxml_bytes) < 6:
        return {"sync_key": "0"}

    SWITCH_PAGE = 0x00
    END = 0x01
    STR_I = 0x03
    CP_FOLDERHIERARCHY = 0x07
    FH_SYNCKEY = 0x12

    sync_key = "0"
    cp = 0

    # Skip WBXML header (version, public ID, charset, string table length + table bytes)
    i = 0
    if len(wbxml_bytes) >= 4:
        i += 3  # version, public id, charset
        strtbl_len = wbxml_bytes[i]
        i += 1
        if strtbl_len:
            i += strtbl_len

    if i >= len(wbxml_bytes):
        i = 0

    def read_inline_string(buf: bytes, pos: int) -> tuple[str, int]:
        if pos >= len(buf) or buf[pos] != STR_I:
            return "", pos
        pos += 1
        start = pos
        while pos < len(buf) and buf[pos] != 0x00:
            pos += 1
        text = buf[start:pos].decode("utf-8", errors="ignore")
        if pos < len(buf):
            pos += 1
        return text, pos

    while i < len(wbxml_bytes):
        b = wbxml_bytes[i]
        i += 1

        if b == SWITCH_PAGE:
            if i < len(wbxml_bytes):
                cp = wbxml_bytes[i]
                i += 1
            continue

        if b == END:
            continue

        token = b & 0x3F
        has_content = (b & 0x40) != 0

        if cp == CP_FOLDERHIERARCHY and token == FH_SYNCKEY and has_content:
            text, i = read_inline_string(wbxml_bytes, i)
            if text:
                sync_key = text
            break

    return {"sync_key": sync_key or "0"}


def _extract_body_preferences(wbxml_bytes: bytes) -> list:
    """Best-effort parser for AirSyncBase BodyPreference blocks."""
    if not wbxml_bytes:
        return []

    SWITCH_PAGE = 0x00
    END = 0x01
    STR_I = 0x03

    CP_AIRSYNCBASE = 17

    ASB_BODYPREFERENCE = 0x05
    ASB_TYPE = 0x06
    ASB_TRUNCATIONSIZE = 0x07
    ASB_ALLORNONE = 0x08

    prefs = []
    current = None
    cp = 0
    stack = []
    i = 0

    def read_inline_string(buf: bytes, pos: int) -> tuple[str, int]:
        if pos >= len(buf) or buf[pos] != STR_I:
            return "", pos
        pos += 1
        start = pos
        while pos < len(buf) and buf[pos] != 0x00:
            pos += 1
        text = buf[start:pos].decode("utf-8", errors="ignore")
        if pos < len(buf):
            pos += 1
        return text, pos

    while i < len(wbxml_bytes):
        b = wbxml_bytes[i]
        i += 1

        if b == SWITCH_PAGE:
            if i < len(wbxml_bytes):
                cp = wbxml_bytes[i]
                i += 1
            continue

        if b == END:
            if stack:
                tag = stack.pop()
                if tag == "BodyPreference" and current is not None:
                    # Finalize the collected preference (only if type present)
                    if current.get("type") is not None:
                        prefs.append(current)
                    current = None
            continue

        token = b & 0x3F
        has_content = (b & 0x40) != 0

        if cp == CP_AIRSYNCBASE:
            if token == ASB_BODYPREFERENCE:
                stack.append("BodyPreference")
                current = {
                    "type": None,
                    "truncation_size": None,
                    "all_or_none": False,
                }
                continue

            if current is not None:
                if token == ASB_TYPE and has_content:
                    stack.append("BodyPreference:Type")
                    text, i = read_inline_string(wbxml_bytes, i)
                    if text:
                        try:
                            current["type"] = int(text)
                        except ValueError:
                            pass
                    continue

                if token == ASB_TRUNCATIONSIZE and has_content:
                    stack.append("BodyPreference:TruncationSize")
                    text, i = read_inline_string(wbxml_bytes, i)
                    if text:
                        try:
                            current["truncation_size"] = int(text)
                        except ValueError:
                            pass
                    continue

                if token == ASB_ALLORNONE:
                    if has_content:
                        stack.append("BodyPreference:AllOrNone")
                        text, i = read_inline_string(wbxml_bytes, i)
                        current["all_or_none"] = text.strip() == "1"
                    else:
                        current["all_or_none"] = True
                    continue

        if has_content:
            # Unknown element with content: push placeholder and skip inline string if present
            stack.append(None)
            if i < len(wbxml_bytes) and wbxml_bytes[i] == STR_I:
                _, i = read_inline_string(wbxml_bytes, i)

    return prefs


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
