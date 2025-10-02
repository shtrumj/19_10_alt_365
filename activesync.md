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

## Latest Status (Oct 2, 14:26)

### ✅ **MAJOR PROGRESS!**
- Initial handshake works! (0→1)
- iPhone confirms with SyncKey=1
- Server sends items with SyncKey=2

### ❌ **BUT: iPhone Doesn't Display Emails**
Pattern:
```
14:26:44: Client=1 → Server=2 (0 emails, last_synced=35) ← WRONG!
14:26:46: iPhone goes to Ping
14:26:49: Client=1 → Server=2 (4 emails sent, wbxml_length=969)
14:26:51: iPhone goes to Ping again ← Didn't confirm SyncKey=2!
```

**Problem:** iPhone received the email payload but silently rejected it.

### 🔍 Possible Causes
1. **Email body structure** still has issues
2. **Required fields** missing or malformed
3. **Token errors** in Email/AirSyncBase codepages
4. **iPhone cache** - needs account delete/re-add

### 🎯 Next Investigation
- Decode full WBXML byte-by-byte
- Compare with working Z-Push/Grommunio-Sync output
- Check if body content is causing rejection
- Try sending email WITHOUT body to isolate issue
