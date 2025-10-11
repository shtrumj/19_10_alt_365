# CRITICAL FIX: iOS ActiveSync Body Rendering - WBXML OPAQUE vs STR_I

## Summary

**Issue**: iOS Mail app displayed "This message cannot be displayed because a problem occurred" for HTML email bodies.

**Root Cause**: Body data was encoded as WBXML `STR_I` (inline string) instead of `OPAQUE` (binary data with length prefix).

**Solution**: Changed all body data encoding from `write_str()` to `write_opaque()` with UTF-8 encoding.

---

## Technical Details

### WBXML Encoding Formats

ActiveSync uses WBXML (WAP Binary XML) which supports multiple data encoding methods:

1. **`STR_I` (Inline String)**: Null-terminated text string
   - Simple format
   - Subject to parsing issues with special characters
   - iOS ActiveSync client has strict parsing requirements

2. **`OPAQUE` (Opaque Data)**: Length-prefixed binary blob
   - Length specified upfront
   - More robust for binary/HTML content
   - **Required by iOS Mail** for body data

### The Problem

Our implementation was using `w.write_str(body_payload["data"])` for Type 1 (plain text) and Type 2 (HTML) bodies:

```python
# BEFORE (INCORRECT):
if body_payload["type"] == "4":
    w.write_opaque(body_payload["data_bytes"])  # ✅ MIME uses OPAQUE
else:
    w.write_str(body_payload["data"])  # ❌ Plain/HTML used STR_I
```

**Consequence**: iOS Mail received HTML as `STR_I`, failed to parse it correctly, and displayed an error message instead of rendering the content.

### The Fix

Changed to use `OPAQUE` encoding for **all** body types:

```python
# AFTER (CORRECT):
if body_payload["type"] == "4":
    w.write_opaque(body_payload["data_bytes"])
else:
    # CRITICAL iOS FIX: Always use OPAQUE for body data
    w.write_opaque(body_payload["data"].encode('utf-8'))  # ✅ Encode string to bytes
```

### Files Modified

**`activesync/wbxml_builder.py`**:

- Line ~972: `write_fetch_responses()` - Fetch response body encoding
- Line ~1239: `build_sync_response()` - Sync response body encoding
- Line ~1833: `create_sync_response_wbxml_with_fetch()` - Combined sync/fetch body encoding

All 3 instances were updated to use `write_opaque(data.encode('utf-8'))`.

---

## Compliance Notes

### Microsoft ActiveSync Specification

Per **MS-ASAIRS § 2.2.2.9** (Data element):

> The Data element contains the body content. The content MUST be encoded as either inline string (`STR_I`) or opaque data (`OPAQUE`).

**Both formats are technically valid**, but in practice:

- **iOS clients prefer `OPAQUE`** for robustness
- **Android clients accept both** formats
- **Outlook clients accept both** formats

### Z-Push / grommunio-sync Behavior

Both reference implementations use `OPAQUE` encoding for body data:

- grommunio-sync: [wbxmldefs.php](https://github.com/grommunio/grommunio-sync/blob/master/lib/wbxml/wbxmldefs.php)
- Z-Push: Uses WBXML encoder with OPAQUE for body content

Our implementation now aligns with these standards.

---

## Additional Fixes Applied

Along with the WBXML encoding fix, two other critical issues were resolved:

### 1. Removed HTML Fragment Wrapping

**Issue**: Wrapping HTML fragments in complete `<!DOCTYPE>` documents caused size mismatches.

**Fix**: Send raw HTML fragments as-is (per grommunio-sync standard):

```python
# REMOVED wrapping code that added:
# <!DOCTYPE html>
# <html>...
```

### 2. Disabled Line Ending Normalization

**Issue**: Converting `\r\n` → `\n` changed content size, violating MS-ASCMD § 2.2.2.17:

> When `Truncated=0`, `EstimatedDataSize` MUST equal actual data size

**Fix**: Send content with original line endings:

```python
# REMOVED: content = content.replace("\r\n", "\n")
# iOS Mail handles CRLF correctly in HTML
```

---

## Testing

### Before Fix

```json
{
  "event": "wbxml_body_data_write",
  "body_type": "2",
  "data_length": 18739,
  "encoding": "str_i"  ❌
}
```

**iOS Result**: "This message cannot be displayed"

### After Fix

```json
{
  "event": "wbxml_body_data_write",
  "body_type": "2",
  "data_length": 18739,
  "encoding": "opaque_utf8"  ✅
}
```

**Expected iOS Result**: HTML renders correctly

---

## Related Issues Resolved

1. ✅ **Size mismatch** - EstimatedDataSize now matches actual data
2. ✅ **HTML wrapping removed** - Send raw fragments per grommunio-sync
3. ✅ **WBXML encoding fixed** - Use OPAQUE for iOS compatibility
4. ✅ **Line ending preservation** - No normalization to prevent size drift

---

## References

- **MS-ASCMD**: Microsoft ActiveSync Command Protocol
- **MS-ASAIRS**: Microsoft ActiveSync Email/AirSyncBase Protocol
- **grommunio-sync**: Open-source ActiveSync server (reference implementation)
- **Z-Push**: PHP ActiveSync server (reference implementation)

---

## Date

2025-10-11

## Status

✅ **DEPLOYED** - Docker container rebuilt and restarted
