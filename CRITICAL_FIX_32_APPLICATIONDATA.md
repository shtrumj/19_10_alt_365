# CRITICAL FIX #32: ApplicationData Token is WRONG!

## 🔥 THE SMOKING GUN (Latest Expert Analysis)

**THE BUG:**
```python
# Line 159 in minimal_sync_wbxml.py:
# WRONG TOKEN!
output.write(b'\x4F')  # ❌ This is Collection, NOT ApplicationData!
```

**What's actually in the WBXML:**
```
56 (Commands) 
  47 (Add) 
    4D (ServerId) "1:35" 00 01
    4F ← WRONG! This is "Collection" not "ApplicationData"!
    00 02 (SWITCH to Email) 
    4F (Subject) ...
```

**What iOS expects (Microsoft spec):**
```xml
<Commands>
  <Add>
    <ServerId>2:1</ServerId>
    <ApplicationData>  ← REQUIRED WRAPPER!
      <Subject>...</Subject>
      <From>...</From>
      ...
    </ApplicationData>
  </Add>
</Commands>
```

**In WBXML:**
```
56 (Commands)
  47 (Add)
    4D (ServerId) "1:35" 00 01
    5D ← CORRECT! ApplicationData (0x1D + 0x40 = 0x5D)
    00 02 (SWITCH to Email)
    4F (Subject) ...
    ...
    01 ← END ApplicationData
  01 ← END Add
```

---

## 📊 AirSync Codepage 0 Tokens (CORRECTED)

| Base | +Content | Element Name      | Our Code |
|------|----------|-------------------|----------|
| 0x0D | 0x4D     | ServerId          | ✅ 0x4D  |
| 0x0F | 0x4F     | **Collection**    | ❌ Used for ApplicationData! |
| 0x12 | 0x52     | CollectionId      | ✅ 0x52  |
| 0x16 | 0x56     | Commands          | ✅ 0x56  |
| **0x1D** | **0x5D** | **ApplicationData** | ❌ **MISSING!** |
| 0x07 | 0x47     | Add               | ✅ 0x47  |

**THE CONFUSION:**
- Previous expert said: `ApplicationData = 0x0F + 0x40 = 0x4F` ❌ WRONG!
- Correct per MS-ASWBXML: `ApplicationData = 0x1D + 0x40 = 0x5D` ✅

---

## 🎯 THE FIX

### Fix #32-1: Correct ApplicationData Token

```python
# OLD (WRONG):
output.write(b'\x4F')  # ❌ Collection, not ApplicationData!

# NEW (CORRECT):
output.write(b'\x5D')  # ✅ ApplicationData with content (0x1D + 0x40)
```

### Fix #32-2: Ensure Proper Structure

```python
# Commands with content
output.write(b'\x56')  # Commands

# For each email:
    # Add with content
    output.write(b'\x47')  # Add
    
    # ServerId
    output.write(b'\x4D')  # ServerId with content
    output.write(b'\x03')  # STR_I
    output.write(server_id.encode())
    output.write(b'\x00')
    output.write(b'\x01')  # END ServerId
    
    # ✅ FIX #32: ApplicationData wrapper!
    output.write(b'\x5D')  # ApplicationData with content (0x5D)
    
    # SWITCH to Email codepage
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x02')  # Codepage 2 (Email)
    
    # Email fields (Subject, From, To, etc.)
    # ... all email fields ...
    
    # SWITCH to AirSyncBase for Body
    output.write(b'\x00')  # SWITCH_PAGE
    output.write(b'\x0E')  # Codepage 14 (AirSyncBase)
    
    # Body fields (Type, Data, etc.)
    # ... body fields ...
    
    # ✅ END ApplicationData (CRITICAL!)
    output.write(b'\x01')  # END ApplicationData
    
    # END Add
    output.write(b'\x01')  # END Add

# END Commands
output.write(b'\x01')  # END Commands
```

---

## 📝 GOLDEN WBXML SKELETON (Microsoft Spec)

```
03 01 6A 00                     # WBXML header
45                              # Sync (with content)
  5C                            # Collections (with content)
    4F                          # Collection (with content)
      4B 03 "2" 00 01           # SyncKey "2" (NEW key!)
      52 03 "1" 00 01           # CollectionId "1"
      4E 03 "1" 00 01           # Status "1"
      56                        # Commands (with content)
        47                      # Add (with content)
          4D 03 "1:35" 00 01    # ServerId "1:35"
          5D                    # ✅ ApplicationData (with content)
            00 02               # SWITCH_PAGE -> Email (cp 2)
            4F 03 "Subject" 00 01  # Subject
            50 03 "from@..." 00 01 # From
            51 03 "to@..." 00 01   # To
            52 03 "2025-..." 00 01 # DateReceived
            ...                 # Other Email fields
            00 0E               # SWITCH_PAGE -> AirSyncBase (cp 14)
            48                  # Body (with content)
              4A 03 "1" 00 01   # Type "1" (plain text)
              4B 03 "100" 00 01 # EstimatedDataSize
              4C 03 "0" 00 01   # Truncated "0"
              49 03 "Text" 00 01  # Data
            01                  # END Body
          01                    # ✅ END ApplicationData (CRITICAL!)
        01                      # END Add
      01                        # END Commands
    01                          # END Collection
  01                            # END Collections
01                              # END Sync
```

---

## 💥 IMPACT

**Why iOS was looping:**
1. Server sends WBXML with `0x4F` (Collection) instead of `0x5D` (ApplicationData)
2. iOS parses: "Commands > Add > ServerId > **Collection???** > (garbage)"
3. iOS rejects the malformed structure
4. iOS retries with the SAME SyncKey → infinite loop!
5. No emails ever display!

**What happens after FIX #32:**
1. Server sends WBXML with `0x5D` (ApplicationData)
2. iOS parses: "Commands > Add > ServerId > **ApplicationData** > (email fields) ✅"
3. iOS accepts the structure
4. iOS advances SyncKey: 1 → 2 → 3 → ...
5. **Emails DISPLAY!** 📧✅

---

## 🔍 Z-Push Comparison

**Z-Push structure (lib/request/sync.php):**
```php
// Z-Push always wraps item data in ApplicationData
$encoder->startTag(SYNC_COMMANDS);
  $encoder->startTag(SYNC_ADD);
    $encoder->startTag(SYNC_SERVERID);
    $encoder->content($serverid);
    $encoder->endTag();
    
    $encoder->startTag(SYNC_APPLICATIONDATA);  // ← ALWAYS PRESENT!
      // Email fields go here
      $message->encode($encoder);
    $encoder->endTag();  // END ApplicationData
    
  $encoder->endTag();  // END Add
$encoder->endTag();  // END Commands
```

**Token definitions (lib/wbxml/wbxmldefs.php):**
```php
// AirSync codepage 0
define('SYNC_APPLICATIONDATA', 0x1D);  // ← 0x1D, not 0x0F!
```

---

## ✅ VERIFICATION CHECKLIST

After applying FIX #32:

1. **Check WBXML hex** (first 100 bytes of Sync response):
   ```
   Should see: 47 4D ... 01 5D 00 02 ...
                    ^     ^  ^^^^^^^
                    |     |  Switch to Email
                    |     ApplicationData (0x5D)
                    ServerId
   
   NOT: 47 4D ... 01 4F 00 02 ...
                       ^
                       Collection (WRONG!)
   ```

2. **Check logs**:
   - `sync_emails_sent_wbxml_simple` event
   - `wbxml_hex` should contain `5D` after ServerId
   - No more "resend pending" loops!

3. **Check iPhone**:
   - SyncKey advances: 0 → 1 → 2 → 3 → ...
   - Emails appear in Mail app!
   - No more reset to SyncKey=0!

---

## 📚 REFERENCES

- **Microsoft MS-ASCMD**: Sync command structure
  - `<Commands><Add><ServerId>...<ApplicationData>...`
  - https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-ascmd/

- **Microsoft MS-ASWBXML**: Token definitions
  - AirSync codepage 0: ApplicationData = 0x1D
  - https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-aswbxml/

- **Z-Push source**: 
  - `lib/wbxml/wbxmldefs.php`: Token constants
  - `lib/request/sync.php`: Sync response builder

