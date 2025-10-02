# ⚠️ CRITICAL: State Reset Required After WBXML Fixes!

## 🔍 DIAGNOSIS (Oct 2, 19:45)

The iPhone was still looping at `SyncKey=4` even AFTER FIX #32 and #33 were applied!

### Why?

**Pending batch was cached with OLD WBXML!**

```
Current state (before reset):
  sync_key: 4
  pending_sync_key: 4          ← Cached from 15:24 (3:24 PM)
  pending_max_email_id: 35     ← With OLD WBXML (0x16 token)
  last_synced_email_id: 0
```

**Timeline:**
1. **15:04** (3:04 PM): Sent WBXML with `0x16` (wrong) ❌
2. **15:24** (3:24 PM): Sent WBXML with `0x1B` (correct) ✅ **← But iPhone already gave up!**
3. **18:24** (6:24 PM): Rebuilt with FIX #32 + #33
4. **19:44** (7:44 PM): Still looping! **← Resending cached batch from 15:24!**

### The Root Cause

The `pending_sync_key` mechanism caches a batch for idempotent resends. When the iPhone rejected the WBXML at 15:04 and kept retrying, the server created a NEW pending batch at 15:24 with the correct `0x1B` token.

**BUT** the iPhone had already given up and was looping with `SyncKey=0`, triggering the "resend pending" logic, which kept serving the SAME cached batch over and over!

Even though we fixed the code and rebuilt, the **cached pending batch** was never regenerated with the NEW code!

---

## ✅ SOLUTION

**Always reset ALL ActiveSync state after WBXML fixes!**

```python
# Reset script:
state.sync_key = "0"
state.synckey_counter = 0
state.pending_sync_key = None        # ← Clear cached batch!
state.pending_max_email_id = None    # ← Clear cached batch!
state.pending_item_ids = None        # ← Clear cached batch!
state.last_synced_email_id = 0
db.commit()
```

---

## 🎯 TESTING PROCEDURE (CORRECTED)

### After ANY WBXML fix:

1. **Rebuild Docker** with new code
2. **Clear server state** (including pending_* fields!)
3. **Delete iPhone account** (clear client state)
4. **Re-add iPhone account** (fresh sync)

### ❌ What NOT to do:

- ❌ Just rebuild and hope it works
- ❌ Just clear `sync_key` but leave `pending_sync_key`
- ❌ Just delete iPhone account but leave server state

**You need BOTH server AND client state cleared!**

---

## 📊 WBXML TAIL VERIFICATION

From logs:

**Before FIX #33 (15:04):**
```
wbxml_tail: "...737420656d61696c000101000001010116010101"
                                                    ^^
                                                    0x16 (wrong!)
```

**After FIX #33 (15:24):**
```
wbxml_tail: "...737420656d61696c00010100000101011b010101"
                                                  ^^
                                                  0x1B (correct!)
```

**Expected structure:**
```
... 01 01 00 00 01 01 1B 01 01 01
          ^  ^  ^  ^  ^^ ^^ ^^ ^^
          |  |  |  |  |  |  |  └─ END Sync
          |  |  |  |  |  |  └──── END Collections  
          |  |  |  |  |  └─────── END Collection
          |  |  |  |  └────────── MoreAvailable (0x1B) ✅
          |  |  |  └───────────── END Commands
          |  |  └──────────────── END Add
          |  └─────────────────── SWITCH_PAGE 0x00 (AirSync)
          └────────────────────── END ApplicationData
```

The code WAS correct at 15:24, but the cached batch prevented it from working!

---

## 🚀 NEXT STEPS

1. ✅ State has been reset (sync_key=0, pending cleared)
2. 📱 Delete and re-add iPhone Exchange account
3. 👀 Watch logs for progressive SyncKey advancement
4. 📧 Emails should appear!

---

**LESSON LEARNED:** Always clear ALL state (including pending_*) when testing WBXML fixes!

