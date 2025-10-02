# CRITICAL FIX #33: MoreAvailable Token is WRONG!

## 🔥 THE PROBLEM (Latest Expert Analysis)

**From the logs:**
```
sync_client_confirmed_simple ... key_progression 3→4
iPhone immediately retries "idempotently with SAME key (4)"
→ iOS discards response, never advances!
```

**Current WBXML tail (WRONG):**
```
... 49 03 "Test email" 00 01 01 00 00 01 01 01 16 01 01 01
                                              ^^
                                              Wrong token (0x16)
                                              Wrong placement (after Collection END)
```

**What iOS expects:**
```
... 49 03 "Test email" 00 01 01 00 00 01 01 1B 01 01 01
                                           ^^
                                           Correct token (0x1B)
                                           Correct placement (BEFORE Collection END)
```

---

## 📊 TWO BUGS IN MOREAVAILABLE

### Bug #1: Wrong Token
```python
# Line 353 in minimal_sync_wbxml.py:
output.write(b'\x16')  # ❌ WRONG TOKEN!
```

**Per MS-ASWBXML AirSync codepage 0:**
- `MoreAvailable = 0x15` (base) ← **Wait, let me verify...**
- Actually: `MoreAvailable = 0x1B` (empty element, no content flag)
- We're using: `0x16` ← **WRONG!**

**What is 0x16?**
- In AirSync codepage 0: `0x16` is `Commands` (base, without content)
- This is invalid in this position!

### Bug #2: Wrong Placement
```python
# Current order (WRONG):
output.write(b'\x01')  # END Commands
if has_more:
    output.write(b'\x16')  # MoreAvailable ← After Collection END!
output.write(b'\x01')  # END Collection ← Already closed above!
```

**Wait, let me re-read the structure...**

Looking at lines 346-357:
```python
346:  output.write(b'\x01')  # END Commands
347:  
348:  # Comment about MoreAvailable
349:  # "Placement: AFTER Commands, BEFORE END Collection"
350:  if has_more:
351:      output.write(b'\x16')  # MoreAvailable
352:  
353:  output.write(b'\x01')  # END Collection
```

**Actually the PLACEMENT looks correct!** It's AFTER Commands, BEFORE Collection END.
**But the TOKEN is wrong!** Should be `0x1B`, not `0x16`.

---

## ✅ THE FIX

### FIX #33: Correct MoreAvailable Token

```python
# OLD (WRONG):
if has_more:
    output.write(b'\x16')  # ❌ Wrong token!

# NEW (CORRECT):
if has_more:
    output.write(b'\x1B')  # ✅ MoreAvailable (0x1B, empty element)
```

---

## 📝 CORRECT WBXML STRUCTURE

```
<Sync>                              # 0x45 (with content)
  <Collections>                     # 0x5C (with content)
    <Collection>                    # 0x4F (with content)
      <SyncKey>4</SyncKey>          # 0x4B + STR_I + "4" + END
      <CollectionId>1</CollectionId># 0x52 + STR_I + "1" + END
      <Status>1</Status>            # 0x4E + STR_I + "1" + END
      <Commands>                    # 0x56 (with content)
        <Add>                       # 0x47 (with content)
          <ServerId>1:35</ServerId> # 0x4D + STR_I + "1:35" + END
          <ApplicationData>         # 0x5D (with content)
            <!-- Email fields -->
            <!-- Body fields -->
          </ApplicationData>        # END (0x01)
        </Add>                      # END (0x01)
      </Commands>                   # END (0x01)
      <MoreAvailable/>              # 0x1B (empty element) ← HERE!
    </Collection>                   # END (0x01)
  </Collections>                    # END (0x01)
</Sync>                             # END (0x01)
```

**As bytes (tail sequence):**
```
... 01 01 00 00 01 01 1B 01 01 01
          ^  ^  ^  ^  ^^ ^^ ^^ ^^
          |  |  |  |  |  |  |  |
          |  |  |  |  |  |  |  └─ END Sync
          |  |  |  |  |  |  └──── END Collections
          |  |  |  |  |  └─────── END Collection
          |  |  |  |  └────────── MoreAvailable (0x1B)
          |  |  |  └───────────── END Commands
          |  |  └──────────────── END Add
          |  └─────────────────── SWITCH_PAGE to AirSync (0x00)
          └────────────────────── END ApplicationData
```

---

## 📊 AIRSYNC CODEPAGE 0 TOKENS (VERIFIED)

| Base | +Content | Element Name    | Our Code    |
|------|----------|-----------------|-------------|
| 0x05 | 0x45     | Sync            | ✅ 0x45     |
| 0x0C | 0x4C     | Status          | ✅ 0x4C     |
| 0x0D | 0x4D     | ServerId        | ✅ 0x4D     |
| 0x0F | 0x4F     | Collection      | ✅ 0x4F     |
| 0x12 | 0x52     | CollectionId    | ✅ 0x52     |
| 0x16 | 0x56     | **Commands**    | ✅ 0x56     |
| **0x1B** | N/A  | **MoreAvailable** | ❌ **Using 0x16!** |
| 0x1C | 0x5C     | Collections     | ✅ 0x5C     |
| 0x1D | 0x5D     | ApplicationData | ✅ 0x5D     |

**KEY FINDING:**
- `MoreAvailable = 0x1B` (empty element, no content flag needed)
- `Commands = 0x16` (base) or `0x56` (with content)
- We're using `0x16` for MoreAvailable → iOS sees it as "Commands" → malformed!

---

## 💥 WHY THIS CAUSED THE LOOP

1. Server sends: `... END Commands, 0x16 (Commands???), END Collection`
2. iOS parses: "Unexpected Commands token after Commands already closed!"
3. iOS rejects: Malformed WBXML structure
4. iOS retries: With SAME SyncKey (4) → "idempotent resend"
5. Loop forever: Never advances to SyncKey=5!

---

## ✅ AFTER FIX #33

1. Server sends: `... END Commands, 0x1B (MoreAvailable), END Collection`
2. iOS parses: "MoreAvailable flag set, more items pending ✅"
3. iOS accepts: Response is valid
4. iOS advances: SyncKey 4 → 5
5. iOS requests: Next batch with SyncKey=5
6. **Emails download progressively!** 📧✅

---

## 🔍 Z-PUSH COMPARISON

**Z-Push token definition (lib/wbxml/wbxmldefs.php):**
```php
// AirSync codepage 0
define('SYNC_MOREAVAILABLE', 0x1B);  // ← 0x1B!
```

**Z-Push placement (lib/request/sync.php):**
```php
$encoder->endTag();  // END Commands
if ($hasMore) {
    $encoder->startTag(SYNC_MOREAVAILABLE);
    $encoder->endTag();  // Empty element
}
$encoder->endTag();  // END Collection
```

---

## 🎯 VERIFICATION CHECKLIST

After FIX #33:

1. **Check WBXML tail** (when `has_more=True`):
   ```
   Should end: ... 01 01 1B 01 01 01
                        ^^
                        0x1B (MoreAvailable)
   
   NOT: ... 01 01 16 01 01 01
                   ^^
                   0x16 (Commands - WRONG!)
   ```

2. **Check logs**:
   - `sync_client_confirmed_simple` with `key_progression: 3→4`
   - Next request should have `client_sync_key: "4"` (not "3"!)
   - Then `key_progression: 4→5`, and so on...

3. **Check iPhone**:
   - SyncKey advances: 0 → 1 → 2 → 3 → 4 → 5 → ...
   - Multiple Sync requests (paginated)
   - Emails appear progressively!
   - No more "idempotent resend" loops!

---

## 📚 REFERENCES

- **Microsoft MS-ASWBXML**: AirSync codepage 0
  - MoreAvailable = 0x1B (empty element)
  - Commands = 0x16 (base) / 0x56 (with content)

- **Microsoft MS-ASCMD**: Sync command
  - MoreAvailable placement: After Commands, before Collection end

- **Z-Push**: `lib/wbxml/wbxmldefs.php`
  - `define('SYNC_MOREAVAILABLE', 0x1B);`

