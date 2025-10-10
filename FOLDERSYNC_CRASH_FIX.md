# FolderSync Crash Fix - October 10, 2025

## Problem

FolderSync command was returning **500 Internal Server Error**, preventing the client from downloading the folder structure (Inbox, Sent, Drafts, etc.).

### Error in Logs

```
INFO: "POST /Microsoft-Server-ActiveSync?Cmd=FolderSync HTTP/1.0" 500 Internal Server Error
UnboundLocalError: cannot access local variable 'datetime' where it is not associated with a value
File "/app/app/routers/activesync.py", line 1049, in eas_dispatch
```

### User Impact

- iPhone/Outlook couldn't sync folders
- Client stuck at "Verifying account"
- No mailbox structure displayed
- Emails couldn't sync (no folders to sync to)

## Root Cause

**Python variable scoping issue** introduced during OOF implementation.

In the Settings/OOF handler (lines 3410, 3420), I added local imports:

```python
# PROBLEMATIC CODE
if "start_time" in oof_data:
    try:
        from datetime import datetime  # ❌ Local import creates conflict!
        oof_settings.start_time = datetime.fromisoformat(...)
```

This created a **local variable binding** for `datetime` inside the `eas_dispatch` function. When Python encountered `datetime` usage earlier in the function (line 1049), it raised `UnboundLocalError` because it thought `datetime` was a local variable that hadn't been assigned yet.

### Why This Happened

Python determines variable scope at **compile time**, not runtime. When it sees `from datetime import datetime` anywhere in a function, it treats `datetime` as a local variable for the **entire function**, even lines before the import.

## Solution

**Removed the redundant local imports** - `datetime` was already imported at the top of the file:

```python
# Top of file (line 9)
from datetime import datetime, timedelta  # ✅ Already imported!

# Fixed code (lines 3410-3422)
if "start_time" in oof_data:
    try:
        # ✅ Removed: from datetime import datetime
        oof_settings.start_time = datetime.fromisoformat(
            oof_data["start_time"].replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        pass

if "end_time" in oof_data:
    try:
        # ✅ Removed: from datetime import datetime
        oof_settings.end_time = datetime.fromisoformat(
            oof_data["end_time"].replace("Z", "+00:00")
        )
    except (ValueError, AttributeError):
        pass
```

## Fix Applied

1. **Removed duplicate `from datetime import datetime`** (2 instances)
2. **Rebuilt Docker** with `--no-cache` to ensure fresh build
3. **Cleared log** for fresh analysis
4. **Started container** with fixed code

## Verification

### Before Fix

```bash
docker-compose logs email-system | grep FolderSync
# Output: 500 Internal Server Error
# UnboundLocalError: cannot access local variable 'datetime'
```

### After Fix

```bash
# Sync from iPhone/Outlook
docker-compose logs email-system | grep FolderSync
# Expected: 200 OK with folder structure
```

## Testing Instructions

1. **Trigger FolderSync from client**
   - iPhone: Delete and re-add account
   - Outlook: Delete and re-add account
   - Or wait for automatic sync

2. **Check logs for success**

   ```bash
   docker-compose logs -f email-system | grep -i folder
   ```

3. **Verify folder structure**
   - Should see: Inbox, Sent, Drafts, Deleted, etc.
   - No 500 errors
   - HTTP 200 OK responses

4. **Check new log entries**
   ```bash
   tail -f /Users/jonathanshtrum/Dev/4_09_365_alt/logs/activesync/activesync.log
   ```

## Related Files

### Modified

- `app/routers/activesync.py` - Removed duplicate datetime imports (lines 3410, 3420)

### Rebuilt

- Docker image with `--no-cache` flag

## Python Scoping Lesson

### Bad Pattern (Causes UnboundLocalError)

```python
def my_function():
    print(datetime.now())  # ❌ UnboundLocalError!

    # ... 1000 lines later ...

    if some_condition:
        from datetime import datetime  # Creates local binding!
```

### Good Pattern (Works Correctly)

```python
from datetime import datetime  # Import at top

def my_function():
    print(datetime.now())  # ✅ Works!

    if some_condition:
        # Use the already-imported datetime
        result = datetime.fromisoformat(...)
```

## Status

✅ **FolderSync Fix Applied**

- Duplicate imports removed
- Docker rebuilt with `--no-cache`
- Container running healthy
- Log cleared for fresh analysis

⏳ **Testing Needed**

- Sync from iPhone/Outlook
- Verify folder structure downloads
- Confirm no 500 errors

## Error Prevention

To prevent similar issues in the future:

1. **Never use local imports** inside large functions
2. **Always import at module top** (PEP 8 standard)
3. **Run linter** to catch scoping issues
4. **Test all commands** after major changes

## Timeline

- **10:10 UTC**: User reported folder structure not downloading
- **10:15 UTC**: Identified `UnboundLocalError` in logs
- **10:20 UTC**: Found duplicate `datetime` imports in OOF handler
- **10:25 UTC**: Removed duplicate imports
- **10:30 UTC**: Rebuilt Docker with `--no-cache`
- **10:35 UTC**: Container started, log cleared, ready for testing

---

**Fix Date**: October 10, 2025  
**Issue**: FolderSync 500 error due to variable scoping  
**Solution**: Removed duplicate datetime imports  
**Status**: Fixed, ready for client testing
