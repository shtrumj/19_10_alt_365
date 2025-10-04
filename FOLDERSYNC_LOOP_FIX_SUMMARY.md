# FolderSync Loop Fix - Summary

## Problem
iPhone was stuck in a FolderSync loop, continuously sending `SyncKey=0` requests but never progressing to email synchronization.

## Root Cause Analysis

### Issue 1: Server-Client State Desync
- **Server state**: FolderSync `sync_key="1"`, Inbox `sync_key="2"`
- **Client state**: iPhone cached `sync_key="0"` and kept resending it
- **Result**: Server thought everything was synced, but iPhone was stuck at initial setup

### Issue 2: FolderSync Handler Not Executing
- Server logged `"request_received"` for FolderSync commands
- **NO response logs** (`"foldersync_initial_wbxml_response"`, `"zpush_recovery"`, etc.)
- **Diagnosis**: Old Docker image was running, Z-Push fix not deployed

### Issue 3: Client-Side Caching
- iPhone stores ActiveSync state locally
- Even after server state reset, iPhone continued sending old cached `SyncKey=0`
- This is standard ActiveSync client behavior to recover from crashes

## Solutions Applied

### Solution 1: Z-Push Inspired FolderSync Fix (Code Change)
**File**: `/Users/jonathanshtrum/Downloads/365/app/routers/activesync.py`
**Lines**: 672-683

```python
# Z-Push Fix: ALWAYS reset to 1 when client sends 0, regardless of server state
# This allows recovery from desync situations where server is ahead
old_sync_key = state.sync_key
state.sync_key = "1"
db.commit()
_write_json_line("activesync/activesync.log", {
    "event": "foldersync_initial_sync_key_updated", 
    "device_id": device_id,
    "old_sync_key": old_sync_key,
    "new_sync_key": "1",
    "zpush_recovery": old_sync_key != "0"
})
```

**Key Change**: Previously, the code only updated `sync_key` if it was `"0"` in the database. Now it **always** resets to `"1"` when client sends `SyncKey=0`, allowing recovery from desync.

### Solution 2: Diagnostic Test Script
**File**: `/Users/jonathanshtrum/Downloads/365/test_scripts/test_foldersync_loop_fix.py`

**Purpose**:
- Detect FolderSync loop conditions
- Check server state consistency
- Verify WBXML response format
- Apply database fixes if needed

**Usage**:
```bash
docker exec 365-email-system python3 /app/test_foldersync_loop_fix.py
```

### Solution 3: Force Docker Container Rebuild
**Command**:
```bash
docker-compose up -d --build --force-recreate email-system
```

**Why Needed**: The container was running old code; rebuild ensures Z-Push fix is deployed.

## Expected Behavior After Fix

1. **iPhone sends**: `FolderSync` with `SyncKey=0`
2. **Server detects**: Client is at `0`, server might be ahead (e.g., at `"1"`)
3. **Server logs**: `"zpush_recovery": true` (if server was ahead)
4. **Server responds**: `SyncKey="1"` with full folder hierarchy (Inbox, Sent, Drafts, etc.)
5. **iPhone receives**: Folder list and updates its local state to `SyncKey="1"`
6. **iPhone progresses**: Sends `Sync` commands for Inbox to retrieve emails

## Manual iPhone Actions Required

The server-side fix is now deployed, but the iPhone's cached state needs to be cleared:

### Option A: Toggle Mail Account (Recommended)
1. Settings → Mail → Accounts → `owa.shtrum.com`
2. Toggle **Mail** switch OFF
3. Wait 5 seconds
4. Toggle **Mail** switch ON
5. iPhone will reconnect and trigger FolderSync

### Option B: Pull to Refresh
1. Open **Mail app**
2. Select the ActiveSync account mailbox
3. Pull down to refresh
4. iPhone will retry FolderSync

### Option C: Remove and Re-add Account (Last Resort)
1. Settings → Mail → Accounts → `owa.shtrum.com`
2. Delete Account
3. Add Account → Microsoft Exchange
4. Enter credentials and server details

## Verification Steps

After iPhone triggers sync, check logs:

```bash
tail -f logs/activesync/activesync.log | grep -E "(foldersync|zpush_recovery|sync_initial)"
```

**Expected logs**:
1. `"event": "request_received", "command": "foldersync"`
2. `"event": "foldersync_initial_sync_key_updated", "zpush_recovery": true`
3. `"event": "foldersync_initial_wbxml_response", "sync_key": "1"`
4. `"event": "request_received", "command": "sync"`
5. `"event": "sync_initial_WITH_ITEMS", "email_count_sent": 1`

## Current Status

- ✅ **Z-Push fix applied** to `app/routers/activesync.py`
- ✅ **Docker container rebuilt** with fix
- ✅ **Diagnostic script created** and tested
- ⏳ **Waiting for iPhone** to trigger new FolderSync request
- ⏳ **Manual iPhone action required** (pull-to-refresh or toggle account)

## Next Steps

1. **User action**: Manually trigger sync on iPhone (see options above)
2. **Verify logs**: Confirm `"zpush_recovery"` and `"foldersync_initial_wbxml_response"` appear
3. **Monitor email sync**: Check for `"sync_initial_WITH_ITEMS"` and `"email_count_sent"`
4. **Confirm iPhone mailbox**: Emails should start appearing in batches

## References

- **Z-Push**: Open-source ActiveSync implementation that inspired this fix
- **ActiveSync Spec**: MS-ASCMD section 2.2.3.170.2 (FolderSync command)
- **Loop Detection**: Based on Z-Push's sync state machine recovery logic

---

**Created**: 2025-10-04T14:30:00Z
**Last Updated**: 2025-10-04T14:30:00Z
**Status**: Fix deployed, awaiting iPhone retry

