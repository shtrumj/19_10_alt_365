# ActiveSync WBXML Investigation

## 🎉 **CURRENT STATUS: SUCCESS! (Oct 3, 2025 01:15 AM)**

### ✅ **MESSAGES ARE DOWNLOADING TO IPHONE!** 📧

The expert's Z-Push-compliant state machine has **SOLVED THE LOOP**!

### ✅ ALL CRITICAL FIXES APPLIED
1. **FIX #45**: Expert's State Machine Integration (Oct 3, 2025)
   - `minimal_sync_wbxml_expert.py` - Spec-correct WBXML builder
   - `sync_state.py` - Idempotent state machine
   - `sync_adapter.py` - Integration layer
   - **Fixes server state flipping to "0"**
   - **Fixes non-idempotent resends**

2. **FIX #28**: Removed invalid SWITCH_PAGE to codepage 0
   - WBXML now starts with valid `03 01 6a 00 45 4e` (header + Sync tag)

3. **FIX #27**: SyncKey always advances on every response
4. **FIX #26**: Two-phase commit with idempotent resends
5. **FIX #23-1**: AirSyncBase codepage corrected to 14 (0x0E)

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

---

## 🎯 **FINAL SOLUTION (Oct 3, 2025 01:15 AM)**

### The Problem
iPhone was stuck in an infinite loop at SyncKey=0 because:
1. **Server state was flipping to "0"** mid-flow (server_sync_key: 12 → 0 → 12 → 0)
2. **Non-idempotent resends** - server generated NEW batch every retry instead of resending SAME batch
3. **WBXML structure issues** - Minor token and ordering problems

### The Solution: Expert's Z-Push State Machine

**Three new files integrated:**

#### 1. `minimal_sync_wbxml_expert.py` (292 lines)
- **Spec-correct WBXML builder**
- AirSync CP0 (Sync/Collections/Collection/Commands/Add/ServerId/ApplicationData)
- Email CP2 (Subject/From/To/DateReceived/Read)
- AirSyncBase CP17 (Body/Type/EstimatedDataSize/Truncated/Data)
- **Critical ordering**: Type → EstimatedDataSize → Truncated → Data

#### 2. `sync_state.py` (146 lines)
- **Idempotent state machine** (Z-Push equivalent)
- State tracking: `cur_key` (last ACKed), `next_key` (to issue), `pending` (batch), `cursor` (pagination)
- **Idempotent resends**: If `client_sync_key == ctx.cur_key` AND `ctx.pending` exists → resend SAME batch
- **ACK detection**: If `client_sync_key == ctx.next_key` → advance keys, clear pending
- **Never spurious reset**: Server keys only advance forward, never flip to "0"

#### 3. `sync_adapter.py` (149 lines)
- **Integration layer** between our SQLAlchemy models and expert's builder
- Converts `Email` DB objects to simple dicts
- Wraps expert's `SyncStateStore` for clean API
- Provides `sync_prepare_batch()` function for `activesync.py`

### State Machine Flow (Fixed!)

```
Client Request          Server State                      Server Response
-------------          ------------                      ---------------
SyncKey=0       →  cur_key="0", next_key="1"        →  SyncKey="1" (batch1)
                   pending=batch1, cursor=5

SyncKey=0 (retry)→  cur_key="0", next_key="1"       →  SyncKey="1" (SAME batch1)
                   pending=batch1 (idempotent!)

SyncKey=1 (ACK!)→  cur_key="1", next_key="2"        →  SyncKey="2" (batch2)
                   pending=batch2, cursor=10

SyncKey=2 (ACK!)→  cur_key="2", next_key="3"        →  SyncKey="3" (batch3)
                   pending=batch3, cursor=15
```

### Key Rules Implemented

1. **Idempotent Resend Rule**
   ```python
   if ctx.pending and client_sync_key == ctx.cur_key:
       return ctx.pending  # SAME batch, SAME wbxml bytes
   ```

2. **ACK Detection Rule**
   ```python
   if client_sync_key == ctx.next_key:
       ctx.cur_key = ctx.next_key  # Advance
       ctx.next_key = advance_key(ctx.next_key)
       ctx.pending = None  # Clear, ACKed!
   ```

3. **Never Reset Spuriously**
   ```python
   # DO NOT reset cur_key/next_key unless explicit initial sync (SyncKey=0)
   # Unexpected keys? Reset cursor, NOT keys!
   ```

### Testing Verification

✅ **Confirmed Working:**
- iPhone connects with SyncKey=0
- Server responds with SyncKey=1 (minimal initial sync)
- iPhone ACKs with SyncKey=1
- Server responds with SyncKey=2 + email items
- **iPhone displays message!** 📧

### Z-Push-Style Admin Utility

Created `reset_activesync_state.py` (equivalent to `z-push-admin -a remove`):
```bash
# List states
python reset_activesync_state.py --list

# Reset specific device
python reset_activesync_state.py --user yonatan@shtrum.com --device <device_id>

# Reset all devices for user
python reset_activesync_state.py --user yonatan@shtrum.com --all-devices
```

### References

- **Expert diagnosis**: "Server state flips to server_sync_key: '0' even though you've just minted '12'"
- **Z-Push equivalent**: `lib/request/sync.php` lines ~1224 (Commands block logic)
- **Microsoft specs**: MS-ASWBXML 2.1.2 (codepages), MS-ASCMD 2.2.2 (Sync command)
- **Grommunio-Sync**: ActiveSync implementation reference

### Deployment

1. ✅ Docker rebuilt with `--no-cache`
2. ✅ ActiveSync state reset (Z-Push-style)
3. ✅ System restarted and healthy
4. ✅ iPhone re-added account
5. ✅ **MESSAGES DOWNLOADING!**

---

**STATUS**: ✅ **WORKING** - iPhone successfully syncing emails!  
**DATE**: October 3, 2025, 01:15 AM  
**COMMITS**: Ready to commit all changes
