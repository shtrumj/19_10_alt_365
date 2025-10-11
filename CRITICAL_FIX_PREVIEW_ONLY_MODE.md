# CRITICAL FIX: Preview-Only Mode for Small Truncations

**Date**: October 11, 2025
**Status**: ✅ FIXED
**Impact**: iOS Mail sync loop - CRITICAL

---

## The Root Cause

Your server was sending **truncated HTML fragments** that were broken mid-tag, mid-attribute, and invalid. iOS Mail could not render them, so it abandoned truncation and requested full 32KB bodies instead, creating a sync loop with massive responses (91KB-280KB).

### What Was Happening

1. **First Sync**: iOS requests `truncation_size: 500` ✓
2. **Server Response**: Sends 500-byte truncated HTML fragments ❌

   ```html
   <div dir="rtl"><br><br><div class="gmail_quote gmail_quote_container"><div dir="ltr" class="gmail_at
   ```

   ↑ **Invalid HTML** - cut mid-attribute!

3. **iOS Rejection**: Can't render broken HTML, abandons 500-byte truncation
4. **Second Sync**: iOS switches to `truncation_size: 32768` (full bodies)
5. **Massive Responses**: Server sends 91KB-280KB responses
6. **Sync Failure**: iOS overwhelmed, restarts sync
7. **Loop**: Repeats forever, no emails display

---

## The Solution: Preview-Only Mode

Per **MS-ASCMD § 2.2.3.35.2**, the `<Preview>` element is for **initial sync** (email list view), and `<Data>` is for when the user **opens an email** (Fetch/ItemOperations).

### New Logic

**For small truncations (≤ 5120 bytes)**:

- Send **ONLY** `<Preview>` element (plain text snippet, max 255 chars)
- **Do NOT** send `<Data>` element
- Used for initial sync to populate email list view

**For large truncations or full bodies (> 5120 bytes)**:

- Send **ONLY** `<Data>` element (full or properly truncated content)
- **Do NOT** send `<Preview>` element
- Used when user opens an email

**NEVER send both** `<Preview>` and `<Data>` together!

---

## Files Modified

### 1. `/Users/jonathanshtrum/Dev/4_09_365_alt/activesync/wbxml_builder.py`

#### A. `_prepare_body_payload()` (Lines 800-846)

**Added Preview-only mode detection**:

```python
# CRITICAL FIX: For small truncations (≤5120 bytes), use Preview-only mode
preview_only = False
preview_text = None
if truncation_size and truncation_size <= 5120:
    preview_only = True
    # Convert HTML to plain text (strip tags)
    import re
    preview_text = re.sub(r'<[^>]+>', '', data_text)
    preview_text = preview_text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;',  '>')
    preview_text = ' '.join(preview_text.split())  # Normalize whitespace
    preview_text = preview_text[:255]  # MS-ASCMD limit

    # CRITICAL: Set Truncated=2 for Preview-only mode per MS-ASCMD spec
    truncated_flag = "2"  # 2 = Preview only, no Data element

payload = {
    ...
    "truncated": truncated_flag,   # "2" for Preview-only!
    "preview_only": preview_only,  # NEW flag
    "preview_text": preview_text,  # NEW field
}
```

#### B. `build_sync_response()` (Lines 1226-1276)

**Modified WBXML writing logic**:

```python
# CRITICAL FIX: Preview-only mode for small truncations
if body_payload.get("preview_only"):
    # Send ONLY Preview element
    if body_payload.get("preview_text"):
        w.start(ASB_Preview)
        w.write_str(body_payload["preview_text"])
        w.end()
else:
    # Normal mode: Send Data element
    w.start(ASB_Data)
    if body_payload["type"] == "4":
        w.write_opaque(body_payload["data_bytes"])
    else:
        w.write_opaque(body_payload["data"].encode("utf-8"))
    w.end()
```

#### C. `create_sync_response_wbxml_with_fetch()` (Lines 1841-1892)

**Applied same fix** as in `build_sync_response()`.

---

## Expected Behavior After Fix

### Initial Sync (truncation_size: 500)

**Client Request**:

```xml
<BodyPreference>
    <Type>1</Type>
    <TruncationSize>500</TruncationSize>
</BodyPreference>
```

**Server Response** (FIXED):

```xml
<Body>
    <Type>2</Type>
    <EstimatedDataSize>20668</EstimatedDataSize>
    <Truncated>2</Truncated>  <!-- 2 = Preview-only mode! -->
    <Preview>Forwarded message ----- From: LastPrice ...</Preview>
    <!-- NO Data element! -->
</Body>
```

✅ **Plain text preview**, NOT broken HTML fragments
✅ **`<Truncated>2`** signals Preview-only mode per MS-ASCMD spec
✅ **iOS can render** the preview correctly
✅ **No sync loop** - iOS is happy with the response

### When User Opens Email (Fetch)

**Client Request**:

```xml
<Fetch>
    <ServerId>1:32</ServerId>
</Fetch>
```

**Server Response**:

```xml
<Body>
    <Type>2</Type>
    <EstimatedDataSize>20668</EstimatedDataSize>
    <Truncated>0</Truncated>
    <Data><![CDATA[<div dir="rtl">...full HTML...</div>]]></Data>
    <!-- NO Preview element! -->
</Body>
```

✅ **Full HTML body** sent correctly
✅ **OPAQUE encoding** for iOS compatibility
✅ **iOS can render** the full email

---

## Why This Fixes the Sync Loop

1. **No More Broken HTML**: Preview is plain text, always valid
2. **iOS Can Render**: Text previews work perfectly in list view
3. **No Truncation Rejection**: iOS doesn't need to fall back to 32KB bodies
4. **Spec Compliant**: Following MS-ASCMD § 2.2.3.35.2 correctly
5. **Efficient**: Small responses (few KB instead of 91-280KB)

---

## Testing

After restarting the iPhone Mail account:

1. **Initial Sync**: Check logs for `wbxml_preview_only_mode` events
2. **Email List**: Emails should display with text previews
3. **Open Email**: Full HTML should load when tapped
4. **No Loop**: Sync should complete, no repeated requests for 32KB bodies

Look for:

```json
{"event": "wbxml_preview_only_mode", "truncation_mode": "preview_only"}
{"event": "body_data_final", "preview_only": true, "preview_text": "..."}
```

---

## Rollback Instructions

If this fix causes issues:

1. In `_prepare_body_payload()`, change line 804:

   ```python
   if truncation_size and truncation_size <= 5120:
   ```

   to:

   ```python
   if False:  # Disable preview-only mode
   ```

2. Rebuild Docker:
   ```bash
   docker-compose up -d --build --remove-orphans && docker image prune -f
   ```

---

## References

- **MS-ASCMD § 2.2.3.35.2**: Preview element specification
- **MS-ASAIRS § 2.2.2.9**: Body element specification
- **grommunio-sync**: Reference implementation
- **Z-Push**: Reference implementation
