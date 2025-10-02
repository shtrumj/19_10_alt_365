"""
Grommunio-style SyncKey utilities

Per Grommunio-Sync lib/core/statemanager.php:
- SyncKey format: {UUID}Counter
- Example: {550e8400-e29b-41d4-a716-446655440000}1
- Initial sync uses "0"
"""
import re
import uuid
from typing import Tuple, Optional


def parse_synckey(synckey: str) -> Tuple[Optional[str], int]:
    """
    Parse Grommunio-style synckey {UUID}Counter
    
    Args:
        synckey: Synckey string (e.g. "{uuid}1" or "0")
        
    Returns:
        Tuple of (uuid_str, counter)
        
    Raises:
        ValueError: If synckey format is invalid
    """
    if synckey == "0":
        return None, 0
    
    match = re.match(r'^\{([0-9A-Za-z-]+)\}([0-9]+)$', synckey)
    if not match:
        raise ValueError(f"Invalid synckey format: {synckey}. Expected {{UUID}}Counter or '0'")
    
    return match.group(1), int(match.group(2))


def generate_synckey(counter: int = 1, sync_uuid: Optional[str] = None) -> str:
    """
    Generate Grommunio-style synckey {UUID}Counter
    
    Args:
        counter: Counter value (must be > 0 for valid synckey)
        sync_uuid: UUID string (generates new one if not provided)
        
    Returns:
        Synckey string in {UUID}Counter format or "0"
    """
    if counter == 0:
        return "0"
    
    if not sync_uuid:
        sync_uuid = str(uuid.uuid4())
    
    return f"{{{sync_uuid}}}{counter}"


def bump_synckey(synckey: str) -> str:
    """
    Increment synckey counter
    
    Args:
        synckey: Current synckey
        
    Returns:
        New synckey with incremented counter
        
    Raises:
        ValueError: If synckey format is invalid
    """
    sync_uuid, counter = parse_synckey(synckey)
    
    if sync_uuid is None:
        # Initial sync - generate new UUID
        sync_uuid = str(uuid.uuid4())
        return generate_synckey(1, sync_uuid)
    
    return generate_synckey(counter + 1, sync_uuid)


def has_synckey(synckey: str) -> bool:
    """
    Check if synckey represents an established sync relationship
    
    Per Grommunio HasSyncKey(): returns true if uuid AND counter are set
    
    Args:
        synckey: Synckey to check
        
    Returns:
        True if synckey has UUID and counter > 0, False otherwise
    """
    try:
        sync_uuid, counter = parse_synckey(synckey)
        return sync_uuid is not None and counter > 0
    except ValueError:
        return False

