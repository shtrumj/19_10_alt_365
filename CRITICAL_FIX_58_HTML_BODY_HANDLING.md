# CRITICAL FIX #58: Z-Push-Compliant HTML Body Handling

## Date: October 3, 2025

## Problem
iPhone was showing **"This message has not been downloaded from the server"** when trying to view HTML email bodies, despite the server sending WBXML responses with email data.

## Root Causes

### 1. Missing `AirSyncBase:NativeBodyType` Token
- **Issue**: Z-Push includes `AirSyncBase:NativeBodyType` (CP17 token 0x16) alongside the body so iOS knows whether the native payload is HTML (2) or plain text (1).
- **Impact**: iOS couldn't determine the correct renderer for the body content.

### 2. No Body Type Selection Logic
- **Issue**: Code was choosing body content ad-hoc without a standardized selection mechanism based on `BodyPreference`.
- **Impact**: Inconsistent behavior between Add, Fetch, and different body types.

### 3. Global `Content-Type` Header
- **Issue**: `_eas_headers()` was setting `Content-Type: application/vnd.ms-sync.wbxml` globally.
- **Impact**: iOS could get into a weird state when receiving responses like Provision (which should be XML, not WBXML).

### 4. Inconsistent Body Encoding Declaration
- **Issue**: While `InternetCPID=65001` (UTF-8) was already correct in most places, it wasn't consistently declared everywhere.
- **Impact**: Potential encoding confusion on iOS.

## Expert Recommendations

The expert provided a detailed analysis comparing our implementation to Z-Push and MS-ASWBXML specifications, highlighting:

1. **AirSyncBase:NativeBodyType is required** after the `<Body>` element
2. **Body selection logic** must honor client `BodyPreference` (Type 2=HTML preferred, Type 1=Plain preferred)
3. **No global Content-Type** - each response must set its own media type
4. **Correct token order** - already implemented: Type → EstimatedDataSize → Truncated → Data

## Fixes Applied

### 1. Added `ASB_NativeBodyType` Token
```python
# AirSyncBase (CP 17)
ASB_Type              = 0x06
ASB_Body              = 0x0A
ASB_Data              = 0x0B
ASB_EstimatedDataSize = 0x0C
ASB_Truncated         = 0x0D
ASB_NativeBodyType    = 0x16  # ✅ NEW - iOS expects this!
```

### 2. Implemented `_select_body_content()` Helper
```python
def _select_body_content(em: Dict[str, Any], body_type_preference: int = 2) -> tuple[str, int]:
    """
    Choose body content according to BodyPreference:
    - 2 => HTML preferred (if available), else plain
    - 1 => Plain preferred (if available), else HTML
    Returns (content, native_type), where native_type: 1=Plain, 2=HTML
    """
    html = str(em.get("body_html") or em.get("html") or "")
    plain = str(em.get("body") or em.get("preview") or "")
    if body_type_preference == 1:
        content = plain or html
        native = 1 if plain else 2 if html else 1
    else:
        content = html or plain
        native = 2 if html else 1 if plain else 1
    return content, native
```

### 3. Updated All WBXML Builders

**In `build_sync_response()` (Add commands):**
```python
# Prefer HTML body if available; otherwise plain text
content, native_type = _select_body_content(em, body_type_preference=2)
body_bytes = content.encode("utf-8")

# AirSyncBase <Body> (always include) with preference/truncation
w.page(CP_AIRSYNCBASE)
w.start(ASB_Body)
# ORDER MATTERS: Type → EstimatedDataSize → Truncated → Data
w.start(ASB_Type);              w.write_str("2" if native_type == 2 else "1"); w.end()
w.start(ASB_EstimatedDataSize); w.write_str(size if content else "0");         w.end()
w.start(ASB_Truncated);         w.write_str("0");                               w.end()
w.start(ASB_Data);              w.write_str(content if content else "");        w.end()
w.end()  # </Body>
# Native body type hint (as Z-Push does)
w.page(CP_AIRSYNCBASE)
w.start(ASB_NativeBodyType); w.write_str("2" if native_type == 2 else "1"); w.end()
```

**In `write_fetch_responses()` (Fetch commands):**
```python
# AirSyncBase Body — honor client BodyPreference and truncation
content, native_type = _select_body_content(em, body_type_preference)
body_bytes = content.encode("utf-8")

# ... Body structure ...

w.cp(CP_AIRSYNCBASE)
w.start(ASB_NativeBodyType); w.write_str("2" if native_type == 2 else "1"); w.end()
```

**In `create_sync_response_wbxml_with_fetch()` (combined):**
- Same approach as above for both Add and Fetch paths

### 4. Removed Global `Content-Type` Header
```python
def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses (POST).
    
    CRITICAL FIX #31: Echo the client's requested protocol version!
    iOS expects MS-ASProtocolVersion (singular) to match what it sent.
    
    NOTE: Do NOT set a global Content-Type header; each endpoint sets its own media_type
    """
    headers = {
        # MS-ASHTTP required headers
        "MS-Server-ActiveSync": "14.1",
        "X-MS-Server-ActiveSync": "14.1",
        "Server": "365-Email-System",
        "Allow": "OPTIONS,POST",
        # ❌ REMOVED: "Content-Type": "application/vnd.ms-sync.wbxml",
        # MS-ASHTTP performance headers
        "Cache-Control": "private, no-cache",
        ...
    }
```

Each response now sets its own `media_type`:
- Sync/FolderSync/Ping: `application/vnd.ms-sync.wbxml`
- Provision: `application/xml`
- Options: No body

## Testing & Verification

### What to Test
1. **Send a new HTML email** to `yonatan@shtrum.com` with:
   - HTML formatting (bold, italic, colors)
   - Multiple paragraphs
   - Links
   - Images (if supported)

2. **Check iPhone Mail app**:
   - Email should automatically appear (Push notifications working)
   - Open the email
   - **Should show full HTML rendering** (not "This message has not been downloaded")
   - No more plain text fallback

3. **Verify in logs**:
   ```bash
   ./monitor_push.sh
   # OR
   tail -f logs/activesync/activesync.log | jq .
   ```

   Look for:
   - `sync_emails_sent_wbxml_simple` events with large payloads
   - No "This message has not been downloaded" errors from iOS

### Expected WBXML Structure
```
<Sync>
  <Collections>
    <Collection>
      <SyncKey>62</SyncKey>
      <CollectionId>1</CollectionId>
      <Class>Email</Class>
      <Status>1</Status>
      <Commands>
        <Add>
          <ServerId>1:48</ServerId>
          <ApplicationData>
            [CP 2: Email]
            <Subject>Test HTML</Subject>
            <From>sender@example.com</From>
            <To>yonatan@shtrum.com</To>
            <DateReceived>2025-10-03T15:30:00.000Z</DateReceived>
            <MessageClass>IPM.Note</MessageClass>
            <InternetCPID>65001</InternetCPID>
            <Read>0</Read>
            [CP 17: AirSyncBase]
            <Body>
              <Type>2</Type>  <!-- HTML -->
              <EstimatedDataSize>1234</EstimatedDataSize>
              <Truncated>0</Truncated>
              <Data><![CDATA[<html>...]]></Data>
            </Body>
            <NativeBodyType>2</NativeBodyType>  <!-- ✅ THIS IS THE KEY FIX -->
          </ApplicationData>
        </Add>
      </Commands>
    </Collection>
  </Collections>
</Sync>
```

## References

### Microsoft Specifications
- **MS-ASWBXML 2.1.2.1.18**: AirSyncBase (Code Page 17) token values including `Body`, `Type`, `EstimatedDataSize`, `Truncated`, `NativeBodyType`
- **MS-ASWBXML 2.1.2.1.3**: Email (Code Page 2) token values including `InternetCPID=0x39`
- **MS-ASCMD**: `airsyncbase:Body` required child elements and order

### Z-Push Implementation
- Z-Push always includes `AirSyncBase:NativeBodyType` after the `<Body>` element
- Z-Push uses `InternetCPID=65001` (UTF-8) consistently
- Z-Push honors client `BodyPreference` to choose HTML vs plain text

## Status

✅ **IMPLEMENTED** - October 3, 2025

- [x] Added `ASB_NativeBodyType = 0x16` token
- [x] Implemented `_select_body_content()` helper
- [x] Updated `build_sync_response()` to use helper and add `NativeBodyType`
- [x] Updated `write_fetch_responses()` to use helper and add `NativeBodyType`
- [x] Updated `create_sync_response_wbxml_with_fetch()` to use helper and add `NativeBodyType`
- [x] Removed global `Content-Type` header from `_eas_headers()`
- [x] Rebuilt Docker container
- [x] Restarted Docker compose stack
- [x] Committed changes to git

## Next Steps

1. **User to test on iPhone**:
   - Send HTML email to test account
   - Verify full HTML rendering appears immediately
   - Confirm no "This message has not been downloaded" errors

2. **If still issues**:
   - Provide full `activesync.log` snippet showing the Sync request and response
   - Expert can analyze WBXML hex dump to verify token order and values

3. **Future enhancements**:
   - Implement actual truncation logic (currently always `Truncated=0`)
   - Parse and honor client `BodyPreference` from incoming WBXML
   - Support `Email2:MIME` for full RFC-822 MIME messages

## Related Fixes
- **CRITICAL FIX #57**: Event-driven push notifications (Ping command)
- **CRITICAL FIX #56**: Z-Push-compliant HTML body imports and structure
- **CRITICAL FIX #31**: Protocol version negotiation

