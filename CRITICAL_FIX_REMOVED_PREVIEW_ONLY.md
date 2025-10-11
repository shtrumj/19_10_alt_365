# CRITICAL FIX: Removed Non-Standard Preview-Only Mode (Truncated=2)

**Date**: October 11, 2025  
**Issue**: iOS Mail not downloading emails - stuck in sync loop  
**Root Cause**: Server using non-standard `Truncated=2` "Preview-only" mode that confused iOS clients

---

## The Problem

### What Was Happening

1. **iOS requests small truncation** (500 bytes) for initial sync list view
2. **Server sends conflicting response:**
   - `<Type>2</Type>` (HTML body type)
   - `<Truncated>2</Truncated>` (Preview-only mode)
   - `<Preview>` element with **plain text** (not HTML!)
   - No `<Data>` element

3. **iOS gets confused:**
   - Expected HTML in `<Data>` element
   - Got plain text in `<Preview>` element
   - Can't render the email

4. **iOS recovery logic:**
   - Switches to 32KB truncation hoping to get real HTML
   - Server sends FULL untruncated bodies for multiple emails
   - Response too large, sync fails

5. **Loop repeats indefinitely** ❌

### Why Preview-Only Mode Failed

The `Truncated=2` "Preview-only" mode is **not standard ActiveSync behavior**:

- ❌ Not used by grommunio-sync
- ❌ Not used by z-push
- ❌ Not well-supported by iOS Mail
- ❌ Conflicts with `Type` specification (HTML vs plain text)
- ❌ Violates ActiveSync protocol expectations

---

## The Solution

### What Standard Servers Do

**grommunio-sync and z-push** use **simple truncation**:

1. ✅ Truncate the **actual HTML content** to requested size
2. ✅ Send truncated HTML in `<Data>` element
3. ✅ Set `<Truncated>1</Truncated>` (standard truncation)
4. ✅ **Never** use `<Preview>` element
5. ✅ **Never** use `<Truncated>2</Truncated>`

### Changes Made

#### 1. Removed Preview-Only Logic (`_prepare_body_payload`)

**Before:**

```python
preview_only = False
preview_text = None
if truncation_size and truncation_size <= 5120:
    preview_only = True
    preview_text = re.sub(r"<[^>]+>", "", data_text)  # Strip HTML
    preview_text = preview_text[:255]
    truncated_flag = "2"  # NON-STANDARD!
```

**After:**

```python
# REMOVED: Preview-only mode (Truncated=2) is NOT standard and breaks iOS
# Standard servers simply truncate HTML and send in Data element
```

Now the code just uses standard truncation:

- Truncates HTML at UTF-8 byte boundary
- Sets `truncated_flag = "1"`
- Sends truncated HTML in `<Data>` element

#### 2. Simplified WBXML Builder (`build_sync_response`)

**Before:**

```python
if body_payload.get("preview_only"):
    # Send ONLY Preview element
    w.start(ASB_Preview)
    w.write_str(body_payload["preview_text"])
    w.end()
else:
    # Normal mode: Send Data element
    w.start(ASB_Data)
    w.write_opaque(body_payload["data"].encode("utf-8"))
    w.end()
```

**After:**

```python
# STANDARD TRUNCATION: Always send Data element with truncated HTML
w.start(ASB_Data)
w.write_opaque(body_payload["data"].encode("utf-8"))
w.end()
```

#### 3. Updated Payload Validation

**Before:**

```python
assert payload["truncated"] in ("0", "1", "2"), ...
```

**After:**

```python
# Truncated must be "0" or "1" (standard truncation only)
# We don't use Truncated=2 as it's non-standard and breaks iOS
assert payload["truncated"] in ("0", "1"), ...
```

---

## Expected Behavior Now

### Initial Sync (Small Truncation: 500 bytes)

**iOS Request:**

```xml
<BodyPreference>
  <Type>1</Type>  <!-- Client asks for plain text -->
  <TruncationSize>500</TruncationSize>
</BodyPreference>
```

**Server Response:**

```xml
<Body>
  <Type>2</Type>  <!-- We send HTML (better quality) -->
  <EstimatedDataSize>20668</EstimatedDataSize>
  <Truncated>1</Truncated>  <!-- Standard truncation -->
  <Data>
    <!-- First 500 bytes of HTML content (properly truncated at UTF-8 boundary) -->
    <div dir="rtl"><br><br><div class="gmail_quote">...
  </Data>
</Body>
```

### When User Opens Email

**iOS Request:**

```xml
<BodyPreference>
  <Type>2</Type>
  <TruncationSize>32768</TruncationSize>  <!-- Larger request -->
</BodyPreference>
```

**Server Response:**

```xml
<Body>
  <Type>2</Type>
  <EstimatedDataSize>20668</EstimatedDataSize>
  <Truncated>0</Truncated>  <!-- Full body fits -->
  <Data>
    <!-- Complete HTML content -->
    <div dir="rtl"><br><br>...full email...</div>
  </Data>
</Body>
```

---

## Testing

1. **Delete and re-add** the account on your iPhone
2. **Expected result:**
   - Initial sync shows 5 emails with truncated previews ✅
   - Opening an email downloads full content ✅
   - No sync loop ✅
   - HTML renders correctly ✅

---

## Files Modified

- `activesync/wbxml_builder.py`:
  - Removed `preview_only` logic from `_prepare_body_payload`
  - Simplified `build_sync_response` to always use Data element
  - Simplified `create_sync_response_wbxml_with_fetch` to always use Data element
  - Updated `_validate_body_payload` to reject `Truncated=2`

---

## Key Takeaways

1. **Follow the standard:** grommunio-sync and z-push use simple truncation, not Preview mode
2. **Always send `<Data>`:** Never use `<Preview>` for truncated bodies
3. **Use `Truncated=1`:** Standard truncation flag, well-supported
4. **Avoid `Truncated=2`:** Non-standard, breaks iOS Mail
5. **Keep it simple:** Truncate HTML, send in Data element, done ✅
