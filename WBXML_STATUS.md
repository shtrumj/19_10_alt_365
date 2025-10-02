# WBXML ActiveSync Status Report

## ✅ FIXES COMPLETED

### FIX #28: Invalid SWITCH_PAGE Removed
**Problem:** WBXML had `03 01 6a 00 00 00 45 4e` where the three `00` bytes were:
- `00` - String table length (correct)
- `00 00` - SWITCH_PAGE to codepage 0 (INVALID!)

After header, first token was `00` (codepage 0), which is NOT a valid tag token!

**Solution:** Removed SWITCH_PAGE since we're already in codepage 0 by default.

**Result:** Now sending `03 01 6a 00 45 4e` - starts directly with Sync tag (0x45) ✅

### FIX #27: SyncKey Always Advances
- SyncKey now advances on every response: 0→1→2→3...
- `state.sync_key` and `state.synckey_counter` are committed before sending
- Pagination tracking via `last_synced_email_id`

### FIX #26: Two-Phase Commit
- Batches are staged as `pending_sync_key` before client confirmation
- Idempotent resends when client retries with old key
- Only commit `last_synced_email_id` when client confirms

## ⚠️ CURRENT ISSUE

**iPhone still looping at SyncKey=0 after FIX #28!**

Pattern:
```
📱 Client: SyncKey=0
📤 Server: SyncKey=1 + Items (pending_sync_key=1)
📱 Client: SyncKey=0 (REJECTS! Loops forever)
```

The WBXML header is now valid (03 01 6a 00 45 4e), but iPhone still rejects the payload.

## 🔍 NEXT INVESTIGATION: Email Body Structure

Per user request: **"Read how body should pass in activesync format - follow Z-Push code bit by bit"**

### Current Body Implementation (minimal_sync_wbxml.py)

```python
# Line 263: Force plain text for testing
body_text = "Test email"  # Ultra simple
body_type = '1'  # 1=Plain text
native_body_type = '1'

# Line 285-286: Switch to AirSyncBase (cp 14)
output.write(b'\x00')  # SWITCH_PAGE
output.write(b'\x0E')  # Codepage 14 (AirSyncBase)

# Line 288-289: Body tag
output.write(b'\x48')  # Body with content (AirSyncBase)

# Line 291-297: Type
output.write(b'\x4A')  # Type with content
output.write(b'\x03')  # STR_I
output.write(body_type.encode())  # '1'
output.write(b'\x00')  # String terminator
output.write(b'\x01')  # END Type

# Line 302-308: EstimatedDataSize
output.write(b'\x49')  # EstimatedDataSize with content
output.write(b'\x03')  # STR_I
output.write(str(len(body_text)).encode())
output.write(b'\x00')
output.write(b'\x01')  # END EstimatedDataSize

# Line 311-317: Truncated
output.write(b'\x4C')  # Truncated with content
output.write(b'\x03')  # STR_I
output.write(b'0')  # 0 = not truncated
output.write(b'\x00')
output.write(b'\x01')  # END Truncated

# Line 320-326: Data
output.write(b'\x49')  # Data with content (SAME TOKEN AS EstimatedDataSize!)
output.write(b'\x03')  # STR_I
output.write(body_text.encode('utf-8'))
output.write(b'\x00')
output.write(b'\x01')  # END Data
```

### 🐛 **POTENTIAL BUG: Data Token is WRONG!**

Line 320 uses `0x49` for Data, but that's the same as EstimatedDataSize!

Per MS-ASWBXML AirSyncBase codepage (14):
- `0x09` = `Data` (base)
- `0x09 + 0x40 = 0x49` = `Data` with content ✅

Wait, that should be correct... Let me check EstimatedDataSize:
- `0x08` = `EstimatedDataSize` (base)
- `0x08 + 0x40 = 0x48` = `EstimatedDataSize` with content

But we're using `0x49` for both! That's the bug!

## 🎯 ACTION ITEMS

1. **FIX #29: Correct Data token**
   - Line 320: Change from `0x49` to `0x49` (wait, that's already correct?)
   - Need to verify the actual token values from MS-ASWBXML

2. **Compare with Z-Push body handling**
   - Check grommunio-sync source for body serialization
   - Verify token sequence and structure
   - Check for any missing fields or incorrect ordering

3. **Verify AirSyncBase codepage tokens**
   - Body: 0x08 → 0x48 with content
   - Type: 0x0A → 0x4A with content
   - EstimatedDataSize: 0x09 → 0x49 with content ❌ WRONG!
   - Data: 0x07 → 0x47 with content
   - Truncated: 0x0C → 0x4C with content

## 📊 WBXML First 20 Bytes (Current)

```
03 01 6a 00  - Header ✅
45           - Sync tag ✅
4e 03 31 00 01  - Status "1" ✅
5c           - Collections ✅
4f           - Collection ✅
4b 03 31 00 01  - SyncKey "1" ✅
52 03 31     - CollectionId "1" (continues...)
```

Structure looks correct! The issue must be in the email payload itself.

## 🔬 DEBUGGING STEPS

1. Capture full WBXML hex from `sync_initial_wbxml` event
2. Decode byte-by-byte and compare with Z-Push output
3. Fix any token mismatches (especially in body content)
4. Test with minimal email (no body) first
5. Gradually add fields until we find the breaking point

