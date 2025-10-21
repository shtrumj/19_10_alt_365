# ActiveSync Loop Fix Summary

## Problem Analysis

The ActiveSync implementation was experiencing an infinite loop where:

1. **Outlook clients** were requesting sync with the same sync key repeatedly
2. **Batch size limiting** was too conservative, resulting in `emails_selected: 0` but `has_more: true`
3. **No loop detection** mechanism existed to break the cycle

### Key Evidence from Logs

```json
{
  "event": "outlook_batch_size_limiting",
  "total_emails_available": 2,
  "emails_selected": 0,
  "batch_size_bytes": 0,
  "max_batch_size_bytes": 50000,
  "has_more": true
}
```

## Root Cause

1. **Size Estimation Too Conservative**: The code estimated email size as `mime_size + 500` bytes, which was often too high
2. **No Loop Detection**: Unlike grommunio-sync, there was no mechanism to detect when the same sync key was requested multiple times
3. **Zero Selection Loop**: When size estimation prevented any emails from being selected, the client would keep requesting the same sync key

## Solution Implemented

### 1. Improved Size Estimation

- **Reduced overhead estimate** from 500 to 200 bytes
- **More accurate size calculation** using actual MIME content size
- **Force at least 1 email** when size estimation is too conservative to prevent infinite loops

### 2. Loop Detection Mechanism

Added comprehensive loop detection similar to grommunio-sync's `lib/core/loopdetection.php`:

```python
def _detect_sync_loop(
    user_id: int,
    device_id: str,
    collection_id: str,
    client_sync_key: str,
    emails_available: int,
    emails_selected: int,
) -> tuple[bool, int]:
```

**Features:**

- **Tracks consecutive zero selections** when emails are available but none are sent
- **Progressive window size reduction** (like grommunio-sync case 3.0)
- **Automatic loop breaking** by reducing window size from 25 to 20 to 15, etc.
- **State reset** on new sync keys

### 3. Integration with Batch Size Limiting

The loop detection is now integrated into the Outlook batch size limiting logic:

```python
# CRITICAL FIX: Apply loop detection and window size reduction
is_loop, suggested_window = _detect_sync_loop(
    current_user.id,
    device_id,
    collection_id,
    client_sync_key,
    len(emails),
    len(emails_to_send)
)

if is_loop and suggested_window > 0:
    # Apply window size reduction to break the loop
    window_size = min(window_size, suggested_window)
```

## Comparison with grommunio-sync

### grommunio-sync Loop Detection Features:

- **Process stack tracking** for multiple devices/users
- **Broken message detection** and handling
- **Progressive size reduction** (case 3.0: reduces from 40+ to 25 items)
- **UUID change detection** for device resets
- **Usage tracking** to prevent duplicate processing

### Our Implementation:

- **Simplified but effective** loop detection for the specific zero-selection issue
- **Progressive window size reduction** similar to grommunio-sync
- **State tracking** per user/device/collection combination
- **Automatic loop breaking** without manual intervention

## Expected Results

1. **Elimination of infinite loops** when Outlook clients encounter large emails
2. **Progressive fallback** to smaller batch sizes when loops are detected
3. **Better logging** with loop detection events for debugging
4. **Maintained compatibility** with existing iOS/Android clients

## Log Events Added

The fix adds several new log events for monitoring:

- `sync_loop_detected`: When a loop is detected
- `sync_loop_window_reduction`: When window size is reduced
- `sync_loop_window_applied`: When the reduced window size is applied
- `outlook_force_single_email`: When forcing a single email to break a loop

## Testing Recommendations

1. **Test with large emails** that previously caused loops
2. **Monitor log events** for loop detection and window size reduction
3. **Verify Outlook compatibility** with various email sizes
4. **Check iOS/Android clients** are not affected by the changes

## Files Modified

- `app/routers/activesync.py`: Added loop detection and improved batch size limiting
- `ACTIVESYNC_LOOP_FIX_SUMMARY.md`: This documentation file

The fix is backward compatible and should resolve the infinite loop issue while maintaining all existing functionality.
