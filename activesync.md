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
