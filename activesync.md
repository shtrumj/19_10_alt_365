# Microsoft ActiveSync WBXML Specification Analysis

## Overview
This document analyzes the Microsoft ActiveSync WBXML specification and compares it with our current implementation to identify discrepancies causing iPhone synchronization issues.

## Microsoft ActiveSync WBXML Specification

### WBXML Header Structure
According to Microsoft MS-ASWBXML specification:
- **Version**: 0x03 (WBXML 1.3)
- **Public ID**: 0x01 (ActiveSync)
- **Charset**: 0x6A (UTF-8)
- **String Table Length**: 0x00 (no string table)

### AirSync Codepage 0 (Primary Namespace)
Key tokens for Sync responses:
- **Sync**: 0x0E + 0x40 (content flag) = 0x4E
- **Status**: 0x0C + 0x40 (content flag) = 0x4C
- **SyncKey**: 0x20 + 0x40 (content flag) = 0x60
- **Collections**: 0x18 + 0x40 (content flag) = 0x58
- **Collection**: 0x0D + 0x40 (content flag) = 0x4D
- **CollectionId**: 0x11 + 0x40 (content flag) = 0x51
- **MoreAvailable**: 0x15 + 0x40 (content flag) = 0x55
- **WindowSize**: 0x1F + 0x40 (content flag) = 0x5F
- **GetChanges**: 0x18 (empty tag, no content flag)
- **Commands**: 0x12 + 0x40 (content flag) = 0x52
- **Add**: 0x0F + 0x40 (content flag) = 0x4F
- **ServerId**: 0x1A + 0x40 (content flag) = 0x5A
- **ApplicationData**: 0x08 + 0x40 (content flag) = 0x48

### Email Codepage 2 (Secondary Namespace)
Key tokens for email properties:
- **Subject**: 0x15 + 0x40 (content flag) = 0x55
- **From**: 0x13 + 0x40 (content flag) = 0x53
- **To**: 0x06 + 0x40 (content flag) = 0x46
- **DateReceived**: 0x07 + 0x40 (content flag) = 0x47
- **Read**: 0x0B + 0x40 (content flag) = 0x4B
- **Importance**: 0x09 + 0x40 (content flag) = 0x49

### Mandatory Sync Response Structure
According to Microsoft specification, a Sync response MUST contain:

1. **WBXML Header** (6 bytes)
2. **Switch to AirSync codepage** (2 bytes: 0x00 0x00)
3. **Sync element** (0x4E)
4. **Status element** (0x4C + value + 0x01)
5. **SyncKey element** (0x60 + value + 0x01)
6. **Collections element** (0x58)
7. **Collection element** (0x4D)
8. **CollectionId element** (0x51 + value + 0x01)
9. **SyncKey element** (0x60 + value + 0x01) - within Collection
10. **MoreAvailable element** (0x55 + value + 0x01)
11. **GetChanges element** (0x18 + 0x01) - empty tag
12. **WindowSize element** (0x5F + value + 0x01)
13. **Commands element** (0x52) - if emails present
14. **Add elements** (0x4F) - for each email
15. **End tags** (0x01) for all opened elements

### Field Value Requirements

#### Status Values
- **1**: Success
- **2**: Invalid request
- **3**: Invalid sync key
- **4**: Protocol error
- **5**: Server error

#### SyncKey Format
- String representation of synchronization state
- Must be numeric (e.g., "0", "1", "2", etc.)
- Client starts with "0" for initial sync
- Server increments for each successful sync

#### CollectionId Format
- String identifier for the folder
- Typically "1" for Inbox
- Must match the folder being synchronized

#### MoreAvailable Values
- **"0"**: No more data available
- **"1"**: More data available

#### WindowSize Values
- Numeric string representing maximum items per response
- Common values: "100", "200", "500"

## Z-Push Implementation Analysis

### Key Findings from Z-Push Source Code
1. **WBXML Structure**: Z-Push follows Microsoft specification exactly
2. **Token Values**: All tokens match Microsoft specification
3. **Element Ordering**: Critical for iPhone compatibility
4. **Codepage Switching**: Must be done correctly for email properties

### Critical Implementation Details
1. **GetChanges Placement**: Must be inside Collection element, not at top level
2. **SyncKey Duplication**: Must appear both at top level and within Collection
3. **Element Ordering**: Status → SyncKey → Collections → Collection → CollectionId → SyncKey → MoreAvailable → GetChanges → WindowSize
4. **Commands Structure**: Only present when emails are available

## Current Implementation Analysis

### Our Current WBXML Structure
```
Header: 03016a000000
Switch: 0000
Sync: 4e
Status: 4c03310001
Top SyncKey: 6003313000
Collections: 01
Collection: 58
CollectionId: 4d51033100
Collection SyncKey: 0160033130
MoreAvailable: 0001550330
GetChanges: 0001
WindowSize: 18015f0331
```

### Identified Issues

#### 1. Incorrect Element Ordering
**Problem**: GetChanges is placed after WindowSize
**Expected**: GetChanges should be immediately after MoreAvailable
**Impact**: iPhone may reject the response due to unexpected element order

#### 2. Missing Commands Structure
**Problem**: No Commands element when emails are present
**Expected**: Commands (0x52) should contain Add elements for each email
**Impact**: iPhone cannot process email data

#### 3. Incorrect Codepage Usage
**Problem**: Email properties may not be using correct codepage
**Expected**: Must switch to codepage 2 for email properties
**Impact**: Email data may not be properly encoded

## Recommendations

### 1. Fix Element Ordering
Move GetChanges to be immediately after MoreAvailable:
```
MoreAvailable → GetChanges → WindowSize
```

### 2. Add Commands Structure
When emails are present, add:
```
Commands (0x52)
  Add (0x4F)
    ServerId (0x5A)
    ApplicationData (0x48)
      [Switch to codepage 2]
      Subject, From, To, DateReceived, Read, Importance
      [Switch back to codepage 0]
```

### 3. Verify Codepage Switching
Ensure proper codepage switching for email properties:
- Switch to codepage 2 (0x00 0x02) before email properties
- Switch back to codepage 0 (0x00 0x00) after email properties

### 4. Test with Minimal Structure
Start with a minimal Sync response containing only mandatory fields:
- Status, SyncKey, Collections, Collection, CollectionId, SyncKey, MoreAvailable, GetChanges, WindowSize

## Next Steps

1. **Implement corrected element ordering**
2. **Add proper Commands structure for emails**
3. **Verify codepage switching**
4. **Test with iPhone to verify acceptance**
5. **Monitor logs for successful synchronization**

## References

- [Microsoft MS-ASWBXML Specification](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-aswbxml/)
- [Z-Push Source Code](https://github.com/Z-Hub/Z-Push)
- [ActiveSync Protocol Documentation](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-aswbxml/)
