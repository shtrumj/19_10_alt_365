# ActiveSync Body Truncation Fix - October 10, 2025

## Problem

ActiveSync clients were not downloading full email bodies. Analysis of logs revealed:

1. **MIME content was being parsed correctly** - Full content lengths detected (e.g., 3872, 7362, 8614 bytes)
2. **Body data was being truncated to ~300-500 bytes** - Making emails unreadable
3. **Client was requesting Type=1 (plain text) with truncation_size=500 bytes** - Way too small!

### Log Evidence

```json
{"event": "body_payload_prep_start", "truncation_size_param": 500}
{"event": "mime_charset_transcoding", "plain_length": 3872, "html_length": 25279}
{"event": "body_content_selected", "selected_content_length": 3872}
{"event": "truncation_check", "truncation_size": 500, "will_truncate": true}
{"event": "body_data_final", "data_length": 376, "truncated": "1"}
```

The server was **correctly honoring the client's request** for 500-byte truncation, but this made emails unreadable.

## Root Cause

The ActiveSync strategy pattern was implementing "honor client's request exactly" for Type 1/2 (plain/HTML) bodies:

```python
# OLD CODE (all strategies)
else:  # Type 1 or 2
    return truncation_size  # Blindly honor client, even if 500 bytes!
```

This meant when clients requested absurdly small truncation sizes (500 bytes), the server would dutifully truncate to that size.

## Solution

Applied a **minimum truncation size of 32KB** for Type 1/2 (text/HTML) bodies across all strategies:

```python
# NEW CODE (all strategies)
else:  # Type 1 or 2 (plain text or HTML)
    # CRITICAL FIX: Apply minimum truncation of 32KB for text bodies
    # Some clients request tiny sizes (500 bytes) which prevents
    # meaningful email content from being displayed
    MIN_TEXT_TRUNCATION = 32768  # 32KB
    if truncation_size is None:
        return None  # Unlimited
    # Honor client's request, but enforce minimum
    return max(truncation_size, MIN_TEXT_TRUNCATION)
```

## Files Modified

1. **activesync/strategies/ios_strategy.py** - Added 32KB minimum for Type 1/2
2. **activesync/strategies/android_strategy.py** - Added 32KB minimum for Type 1/2
3. **activesync/strategies/outlook_strategy.py** - Added 32KB minimum for Type 1/2

## Expected Behavior After Fix

### Before Fix
- Client requests Type=1, truncation=500 bytes
- Server sends 500 bytes of body
- Email appears truncated/unreadable

### After Fix
- Client requests Type=1, truncation=500 bytes
- Server enforces minimum of 32KB (32768 bytes)
- Server sends 32KB of body (or full body if smaller)
- Email displays properly with meaningful content

### Notes

- **Type 4 (MIME) unchanged** - Still capped at 512KB (Z-Push standard)
- **Respects unlimited requests** - If client sends `truncation_size=null`, server respects it
- **Balances client preference with usability** - Honors large requests, enforces minimum for tiny ones

## Testing Instructions

1. Restart the ActiveSync server
2. Clear ActiveSync cache on client (iPhone/Outlook)
3. Perform a new sync
4. Check logs for `effective_truncation` - Should show 32768 instead of 500
5. Verify emails display full content (at least 32KB worth)

## Related Issues

- MIME parsing: ✅ Working correctly
- Body encoding: ✅ Working correctly (charset transcoding)
- Body type selection: ✅ Working correctly
- **Body truncation: ✅ FIXED** (this document)

The only issue was the overly aggressive truncation honoring the client's tiny 500-byte request.

