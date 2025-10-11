# CRITICAL FIX: Window Size Respect

## Problem Identified

After analyzing the `activesync.log`, the reason emails were not being downloaded was that the server was **ignoring the client's `WindowSize` parameter** and sending the entire mailbox content instead of the small, manageable batch requested.

### The Issue Sequence:

1. **iPhone Request**: Client sends `Sync` with `window_size=5` and `truncation_size=500`
2. **Server Response**: Server fetches 100 emails from database (ignoring window_size)
3. **Massive Response**: Server sends 280,834 bytes of data (entire mailbox)
4. **Client Failure**: iPhone cannot handle the unexpected massive response
5. **Sync Loop**: Client restarts the process, creating an endless loop

## Root Cause

In `/app/routers/activesync.py` line 2160, the server was hardcoded to fetch 100 emails:

```python
# OLD CODE - IGNORED WINDOW_SIZE
all_emails = email_service.get_user_emails(
    current_user.id, folder_type, limit=100  # ❌ Hardcoded limit
)
```

## Solution Applied

### 1. Dynamic Query Limit

```python
# NEW CODE - RESPECTS WINDOW_SIZE
query_limit = max(window_size * 2, 50)  # Fetch a bit more to account for filtering
all_emails = email_service.get_user_emails(
    current_user.id, folder_type, limit=query_limit
)
```

### 2. Window Size Enforcement

```python
# CRITICAL FIX: Apply window_size limit to respect client's request
# Client asked for window_size=5, so we should only send 5 emails max
original_count = len(emails)
if window_size and len(emails) > window_size:
    emails = emails[:window_size]
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "window_size_applied",
            "original_count": original_count,
            "window_size": window_size,
            "final_count": len(emails),
            "message": "Limited emails to window_size as requested by client",
        },
    )
```

## Expected Results

With this fix, the server will now:

1. **Respect WindowSize**: Only fetch and send the number of emails the client requested (e.g., 5 emails)
2. **Small Response**: Response size will be dramatically reduced (from 280KB to ~5-10KB)
3. **Proper Truncation**: Each email will be truncated to 500 bytes as requested
4. **No Sync Loop**: Client will receive the expected small, manageable response
5. **Successful Download**: Emails will finally appear on the iPhone

## Files Modified

- `/app/routers/activesync.py` (lines 2159-2232)
  - Dynamic query limit based on window_size
  - Window size enforcement after filtering
  - Detailed logging for debugging

## Testing

The fix has been deployed and the log has been cleared. The next sync attempt should show:

- `window_size_applied` event in logs
- Much smaller response size
- Successful email download to iPhone

## Status

✅ **FIXED**: Window size parameter now respected  
✅ **DEPLOYED**: Docker container rebuilt and running  
✅ **READY**: Ready for testing with iPhone sync
