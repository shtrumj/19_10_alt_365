# WBXML Rejected by iOS - Need Expert Analysis

**Date:** October 2, 2025  
**Issue:** iOS accepts empty Sync responses but rejects responses with actual emails

## Behavior

- ✅ iPhone accepts initial sync (0→1) with no emails
- ✅ iPhone accepts subsequent syncs (1→2→3→4→5→6) with no emails
- ❌ iPhone REJECTS Sync responses with 1 email and loops (client stays at 6, server advances to 7)
- ✅ iPhone goes to PING mode after accepting empty responses

## Full WBXML Hex (iOS Rejected This)

**Length:** 384 bytes (769 chars hex)

```
03016a00454e033100015c4f5003456d61696c00014b0337000152033100014e0331000156474d03313a333500015d00024f034677643a20d7a9d7a0d79420d798d795d791d79420d795d792d79ed7a820d797d7aad799d79ed79420d798d795d791d794202d20d791d799d7aa20d794d797d799d7a0d795d79a20d7b4d7a7d793d79dd7b40001500373687472756d6a40676d61696c2e636f6d00015103796f6e6174616e4073687472756d2e636f6d00015203323032352d31302d30315432313a35333a35352e3030305a00015303796f6e6174616e4073687472756d2e636f6d000154034677643a20d7a9d7a0d79420d798d795d791d79420d795d792d79ed7a820d797d7aad799d79ed79420d798d795d791d794202d20d791d799d7aa20d794d797d799d7a0d795d79a20d7b4d7a7d793d79dd7b40001550331000156033000015c0349504d2e4e6f746500015f03310001000e484a033100014b03313000014c0331000149035465737420656d61696c00010100000101011b010101
```

## Structure Breakdown (First 60 bytes)

```
03 01 6A 00              # WBXML header
45                       # Sync (0x45)
4E 03 31 00 01           # Status="1" (top-level)
5C 4F                    # Collections / Collection
50 03 45 6D 61 69 6C 00 01  # Class="Email"
4B 03 37 00 01           # SyncKey="7"
52 03 31 00 01           # CollectionId="1"
4E 03 31 00 01           # Status="1" (collection-level)
56                       # Commands (0x56)
47                       # Add (0x47)
4D 03 31 3A 33 35 00 01  # ServerId="1:35"
5D                       # ApplicationData (0x5D)
00 02                    # SWITCH_PAGE to Email (codepage 2) ✅
4F 03 ...                # Subject (0x4F) with Hebrew text
```

## Structure Breakdown (Last 30 bytes)

```
... 54 65 73 74 20 65 6D 61 69 6C 00 01 01 00 00 01 01 01 1B 01 01 01
    T  e  s  t     e  m  a  i  l  \0
                                    ^  ^  ^^ ^^ ^  ^  ^  ^^ ^  ^  ^
                                    |  |  |  |  |  |  |  |  |  |  └─ END Sync
                                    |  |  |  |  |  |  |  |  |  └──── END Collections
                                    |  |  |  |  |  |  |  |  └─────── END Collection
                                    |  |  |  |  |  |  |  └────────── MoreAvailable
                                    |  |  |  |  |  |  └───────────── END Commands
                                    |  |  |  |  |  └──────────────── END Add
                                    |  |  |  |  └─────────────────── END ApplicationData
                                    |  |  |  └────────────────────── codepage 0
                                    |  |  └───────────────────────── SWITCH_PAGE
                                    |  └──────────────────────────── END Body
                                    └─────────────────────────────── END Data
```

## Verified Elements

- [x] Header: `03 01 6A 00` (version 1.3, UTF-8, no string table)
- [x] Top-level Status under Sync
- [x] Collection element order: Class → SyncKey → CollectionId → Status
- [x] SWITCH_PAGE to Email (0x00 0x02) immediately after ApplicationData
- [x] Email tokens (Subject=0x4F, From=0x50, To=0x51, DateReceived=0x52, DisplayTo=0x53, ThreadTopic=0x54, Importance=0x55, Read=0x56, MessageClass=0x5C)
- [x] SWITCH_PAGE to AirSyncBase (0x00 0x0E) for Body
- [x] AirSyncBase tokens (Body=0x48, Type=0x4A, EstimatedDataSize=0x4B, Truncated=0x4C, Data=0x49)
- [x] SWITCH_PAGE back to AirSync (0x00 0x00) before closing ApplicationData
- [x] Commands closed (0x01) before MoreAvailable (0x1B)
- [x] All ENDs present
- [x] HTTP Content-Type: application/vnd.ms-sync.wbxml

## Questions for Expert

1. **Is the AirSyncBase Body structure correct?**
   - We have: Type → EstimatedDataSize → Truncated → Data
   - Should it be: Type → Data only?

2. **Is there an issue with the SWITCH_PAGE sequence?**
   - We do: Email fields → SWITCH to ASBase → Body → SWITCH to AirSync
   - Should we SWITCH back to Email after Body, THEN to AirSync?

3. **Are all the Email tokens correct?**
   - We use tokens from MS-ASWBXML Email codepage
   - DisplayTo, ThreadTopic, etc. - are these all required?

4. **Is there a hidden structural issue in the nesting?**
   - Any elements out of order within ApplicationData?
   - Any missing or extra ENDs?

## Test Environment

- Device: iPhone (iOS 16C2/2301.355)
- Protocol: ActiveSync 14.1
- Server: Custom FastAPI implementation
- Reference: Z-Push, Grommunio-Sync, MS-ASCMD, MS-ASWBXML

## Request

**Please analyze the full hex dump byte-by-byte** to identify what iOS is rejecting!

The iPhone is clearly parsing the envelope (accepts empty responses), but something in the email item payload causes silent rejection.

