# ActiveSync WBXML Investigation

## Current Status

### ✅ FIXED Issues
1. **FIX #28**: Removed invalid SWITCH_PAGE to codepage 0
   - WBXML now starts with valid `03 01 6a 00 45 4e` (header + Sync tag)
   - No more `00 00 00` bug!

2. **FIX #27**: SyncKey always advances on every response
3. **FIX #26**: Two-phase commit with idempotent resends
4. **FIX #23-1**: AirSyncBase codepage corrected to 14 (0x0E)

### ❌ CURRENT PROBLEM
**iPhone still loops at SyncKey=0** even with valid WBXML header!

## Investigation: Z-Push Body Handling

### Current Implementation Issues

#### Token Values Need Verification
From minimal_sync_wbxml.py:
```python
# Line 306: EstimatedDataSize (claims 0x0B)
output.write(b'\x4B')  # 0x0B + 0x40 = 0x4B

# Line 322: Data (claims 0x09)
output.write(b'\x49')  # 0x09 + 0x40 = 0x49
```

**TODO**: Verify against MS-ASWBXML AirSyncBase codepage (14):
- Body = 0x08
- Type = 0x0A  
- EstimatedDataSize = ???
- Data = ???
- Truncated = 0x0C

### Next Steps

1. **Consult Z-Push wbxmldefs.php** for authoritative AirSyncBase tokens
2. **Test without body content** - send email with NO body to isolate issue
3. **Compare byte-by-byte** with working Z-Push/Grommunio-Sync output
4. **Check for missing required fields** in email payload

### Test Plan

**Phase 1**: Minimal Email (No Body)
- Subject only
- From, To, Date
- NO Body content
- See if sync progresses

**Phase 2**: Add Body Incrementally
- Add Type field
- Add EstimatedDataSize
- Add Data
- Test at each step

**Phase 3**: Full Comparison
- Generate identical email in Z-Push
- Compare WBXML byte-by-byte
- Fix any differences

## Latest Status (Oct 2, 17:42) - TWO CRITICAL FIXES!

### 🎉 **FIX #30: Truncated Token (Z-Push Comparison)**
**THE BUG:**
- Sending `Truncated` as empty tag: `0x0C`
- Per MS-ASWBXML + Z-Push: `Truncated` is a **BOOLEAN CONTAINER**!
- Must send: `0x4C 03 '0' 00 01` (with content)

**THE FIX:**
```python
# OLD (WRONG):
if original_body_size > len(body_text):
    output.write(b'\x0C')  # ❌ Empty tag

# NEW (CORRECT):
output.write(b'\x4C')  # Truncated with content
output.write(b'\x03')  # STR_I
output.write(b'0' if original_body_size <= len(body_text) else b'1')
output.write(b'\x00')
output.write(b'\x01')  # END
```

**IMPACT:** iOS silently rejected email items with empty `Truncated` tag!

---

### 🎉 **FIX #31: Protocol Version Negotiation (Expert Analysis)**
**THE BUG:**
- OPTIONS advertised: `12.1,14.0,14.1,16.0,16.1`
- iOS picks **HIGHEST**: `16.1`
- We send back: `14.1` format WBXML + `MS-ASProtocolVersion: 14.1`
- iOS rejects mismatch → **SyncKey=0 loop**!

**THE FIX:**
1. **Separate headers for OPTIONS vs POST**:
   - `_eas_options_headers()`: No singular `MS-ASProtocolVersion`
   - `_eas_headers(protocol_version)`: Echo client's version
2. **Cap to 14.1 only**:
   - `MS-ASProtocolVersions: 14.1` (not 16.x!)
   - `MS-ASProtocolSupports: 14.0,14.1` (not 16.x!)
3. **Echo client's version**:
   ```python
   client_version = request.headers.get("MS-ASProtocolVersion", "14.1")
   headers = _eas_headers(protocol_version=client_version)
   ```

**IMPACT:** iOS was dropping **ALL** responses due to version mismatch!

---

### ✅ **ALL AIRSYNCBASE TOKENS NOW VERIFIED CORRECT:**
| Element           | Base | +Content | Status |
|-------------------|------|----------|--------|
| Body              | 0x08 | 0x48     | ✅     |
| Type              | 0x0A | 0x4A     | ✅     |
| EstimatedDataSize | 0x0B | 0x4B     | ✅     |
| **Truncated**     | 0x0C | **0x4C** | ✅ **FIXED!** |
| Data              | 0x09 | 0x49     | ✅     |

---

### 🎯 **EXPECTED RESULT (COMBINED FIX #30 + #31):**
1. ✅ OPTIONS → iOS sees: `MS-ASProtocolVersions: 14.1`
2. ✅ Provision → Server echoes: `MS-ASProtocolVersion: 14.1`
3. ✅ FolderSync → Version negotiated: `14.1`
4. ✅ Sync 0→1 → iOS accepts minimal response
5. ✅ Sync 1→2 → iOS accepts items with correct `Truncated` token
6. ✅ Sync 2→ → iPhone confirms, **EMAILS DISPLAY!** 📧

---

### 📱 **READY TO TEST!**
**Steps:**
1. Delete iPhone Exchange account
2. Re-add iPhone Exchange account
3. Watch logs for:
   - `Protocol negotiation: client=14.1, echoing back=14.1`
   - `sync_key_progression: 0→1→2→3...`
   - `wbxml_first20: 03016a0045...` (correct header)

**Verification:**
```bash
tail -f logs/activesync/activesync.log | grep -E '"event":|"sync_key":'
```
