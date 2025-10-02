# 🔍 Initial Sync Protocol Analysis

## Current Behavior (Line 726 activesync.py)

```python
wbxml = create_minimal_sync_wbxml(
    sync_key=response_sync_key, 
    emails=emails,                    # ← Sending emails!
    collection_id=collection_id, 
    window_size=window_size, 
    is_initial_sync=False             # ← Set to FALSE!
)
```

**Problem**: We pass `is_initial_sync=False` even though `client_sync_key == "0"`!

## What This Means

When `is_initial_sync=False`, `create_minimal_sync_wbxml` includes:
- ✅ GetChanges tag
- ✅ WindowSize tag  
- ✅ Commands block with email data

## What Documentation Says (Line 18-24 minimal_sync_wbxml.py)

```
CRITICAL: Initial sync (SyncKey 0→1) must NOT include:
- Commands block
- GetChanges tag
- WindowSize tag

Per Grommunio-Sync lib/request/sync.php line 1224:
Commands are ONLY sent when HasSyncKey() is true
```

## The Bug

We're calling with `is_initial_sync=False` when we should call with `is_initial_sync=True`!

This causes the initial response to include:
- ❌ Commands block (should be absent)
- ❌ GetChanges tag (should be absent)
- ❌ WindowSize tag (should be absent)
- ❌ Email data (should be absent)

## Correct Initial Sync Response Should Be

```xml
<Sync>
  <Status>1</Status>
  <SyncKey>1</SyncKey>
  <Collections>
    <Collection>
      <Class>Email</Class>
      <SyncKey>1</SyncKey>
      <CollectionId>1</CollectionId>
      <Status>1</Status>
      <!-- NO GetChanges! -->
      <!-- NO WindowSize! -->
      <!-- NO Commands! -->
    </Collection>
  </Collections>
</Sync>
```

**Size**: Should be ~50-60 bytes (not 873 bytes!)

## Expected Flow

1. **iPhone sends**: SyncKey=0 (initial request)
2. **Server responds**: SyncKey=1, NO data, NO Commands (empty response)
3. **iPhone confirms**: SyncKey=1 (acknowledging new key)
4. **Server responds**: SyncKey=2, WITH data, WITH Commands

## The Fix

Change line 726 in activesync.py:

```python
# WRONG (current):
wbxml = create_minimal_sync_wbxml(..., is_initial_sync=False)

# CORRECT (should be):
wbxml = create_minimal_sync_wbxml(..., is_initial_sync=True)
```

## Evidence

✅ **VERIFIED**: Own documentation says no Commands for initial sync
✅ **VERIFIED**: Grommunio-Sync HasSyncKey() check
✅ **VERIFIED**: Current response is 873 bytes (too large for empty response)
❌ **WRONG**: Passing False when should pass True

**Confidence**: 99% this is THE bug preventing sync!

