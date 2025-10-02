# CRITICAL FIX #45: Expert's State Machine Integration

**Date**: October 3, 2025, 01:05 AM  
**Issue**: iPhone looping on SyncKey=11, server state flipping to "0"  
**Root Cause**: Server not persisting SyncKey properly + not resending batches idempotently

---

## 🎯 THE FIX

The expert provided two critical files that solve the looping problem:

### 1. `minimal_sync_wbxml_expert.py` ✅
**Spec-correct WBXML builder** with:
- AirSync CP0 for Sync/Collections/Collection/Commands/Add/ServerId/ApplicationData
- Email CP2 for Subject/From/To/DateReceived/Read  
- AirSyncBase CP17 for Body/Type/EstimatedDataSize/Truncated/Data
- **CRITICAL**: Type → EstimatedDataSize → Truncated → Data order inside Body

### 2. `sync_state.py` ✅
**Idempotent state machine** that fixes:
- ❌ **Problem**: Server generated NEW batch every time client retried with same SyncKey
- ✅ **Solution**: Store `pending` batch, resend SAME batch for same client key
- ❌ **Problem**: Server `sync_key` flipped to "0" mid-flow  
- ✅ **Solution**: Never reset `cur_key` spuriously; only advance on ACK

### 3. `sync_adapter.py` ✅
**Integration layer** that:
- Converts our SQLAlchemy `Email` models to simple dicts
- Wraps expert's in-memory state store
- Provides clean interface: `sync_prepare_batch(...) → SyncBatch`

---

## 📊 HOW IT WORKS

### State Machine Flow

```
Client                    Server State Machine                          Response
------                    --------------------                          --------
SyncKey=0        →  cur_key="0", next_key="1"                    →  SyncKey="1" (emails 1-5)
                    pending=batch1, cursor=5

SyncKey=0 (retry)→  cur_key="0", next_key="1"                    →  SyncKey="1" (SAME batch1)
                    pending=batch1 (idempotent resend!)

SyncKey=1 (ACK!) →  cur_key="1", next_key="2", cursor=10         →  SyncKey="2" (emails 6-10)
                    pending=batch2

SyncKey=2 (ACK!) →  cur_key="2", next_key="3", cursor=15         →  SyncKey="3" (emails 11-15)
                    pending=batch3
```

### Key Rules Implemented

1. **Idempotent Resend**  
   ```python
   if ctx.pending and client_sync_key == ctx.cur_key:
       return ctx.pending  # SAME batch, SAME wbxml bytes
   ```

2. **ACK Detection**  
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

---

## 🔧 INTEGRATION STATUS

### Files Created/Updated

- ✅ `/app/minimal_sync_wbxml_expert.py` - Expert's WBXML builder
- ✅ `/app/sync_state.py` - Expert's state machine
- ✅ `/app/sync_adapter.py` - Our integration layer
- ⏳ `/app/routers/activesync.py` - **TODO**: Replace old logic with:
  ```python
  from ..sync_adapter import sync_prepare_batch
  
  # In Sync command handler:
  batch = sync_prepare_batch(
      db=db,
      user_email=current_user.email,
      device_id=device_id,
      collection_id=collection_id,
      client_sync_key=client_sync_key,
      db_emails=emails,
      window_size=window_size
  )
  
  return Response(
      content=batch.wbxml,
      media_type="application/vnd.ms-sync.wbxml",
      headers={...}
  )
  ```

---

## 🎯 WHY THIS FIXES THE LOOP

### Before (Your Logs)
```json
{"client_sync_key": "11", "server_sync_key": "12"}
{"client_sync_key": "11", "server_sync_key": "0"}  ← Server reset!
{"client_sync_key": "11", "server_sync_key": "12"}
{"client_sync_key": "11", "server_sync_key": "0"}  ← Reset again!
```

### After (Expert's Store)
```json
{"client_key": "11", "cur_key": "11", "next_key": "12", "pending": batch12}
{"client_key": "11", "cur_key": "11", "next_key": "12", "pending": batch12}  ← Resend!
{"client_key": "12", "cur_key": "12", "next_key": "13", "pending": batch13}  ← ACK!
{"client_key": "13", "cur_key": "13", "next_key": "14", "pending": batch14}  ← Progress!
```

**No more resets!** State advances monotonically.

---

## 📝 NEXT STEPS

1. ✅ Created expert's files
2. ✅ Created integration adapter
3. ⏳ **TODO**: Update `activesync.py` Sync handler (line ~749)
4. ⏳ **TODO**: Rebuild Docker with `--no-cache`
5. ⏳ **TODO**: Delete/re-add iPhone account
6. ⏳ **TODO**: Verify SyncKey progression: 0→1→2→3...

---

## 🔍 TESTING CHECKLIST

After integration:

- [ ] Initial sync: client sends `0`, server responds with `1`
- [ ] Client retries `0`: server resends SAME batch with `1` (idempotent)
- [ ] Client ACKs with `1`: server responds with NEW batch, key `2`
- [ ] Pagination: `MoreAvailable` tag present when `cursor < len(emails)`
- [ ] Loop stopped: no more `sync_key` flipping to `0`

---

## 📚 REFERENCES

- Expert's diagnosis: "Server state flips to server_sync_key: '0' even though you've just minted '12'"
- Expert's WBXML spec notes: AirSync CP0, Email CP2, AirSyncBase CP17
- Expert's order requirement: Type → EstimatedDataSize → Truncated → Data (inside Body)
- Z-Push equivalent: `lib/request/sync.php` lines ~1224 (Commands block logic)

---

**STATUS**: Files created, integration pending  
**ETA**: 5-10 minutes to wire into `activesync.py` and rebuild Docker

