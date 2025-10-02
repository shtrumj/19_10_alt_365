# 📜 AUTHORITATIVE WBXML Token Definitions

**Source**: Z-Push wbxmldefs.php (https://github.com/Z-Hub/Z-Push)  
**Date Retrieved**: October 2, 2025  
**Status**: ✅ VERIFIED from official Z-Push repository

---

## AirSync Codepage 0 - AUTHORITATIVE TOKENS

| Hex | Token Name | Z-Push Name | With 0x40 | Our Usage |
|-----|------------|-------------|-----------|-----------|
| 0x05 | Sync | "Synchronize" | 0x45 | ✅ CORRECT |
| 0x06 | Responses | "Replies" | 0x46 | ❌ We call this "Collections" |
| 0x07 | Add | "Add" | 0x47 | ✅ CORRECT |
| 0x08 | Change | "Modify" | 0x48 | ❌ We call this "CollectionId" |
| 0x09 | Delete | "Remove" | 0x49 | ✅ We use for "Status" - CORRECT |
| 0x0A | Fetch | "Fetch" | 0x4A | ✅ We use for "SyncKey" - WRONG NAME! |
| 0x0B | SyncKey | "SyncKey" | 0x4B | ❌ We use for "Commands" |
| 0x0C | ClientId | "ClientEntryId" | 0x4C | ❌ Not used |
| 0x0D | ServerId | "ServerEntryId" | 0x4D | ✅ CORRECT |
| 0x0E | Status | "Status" | 0x4E | ✅ We use for "ApplicationData" - WRONG! |
| 0x0F | Collection | "Folder" | 0x4F | ❌ Not used |
| 0x10 | Class | "FolderType" | 0x50 | ❌ Not used |
| 0x11 | Version | "Version" (deprecated) | 0x51 | ❌ Not used |
| 0x12 | CollectionId | "FolderId" | 0x52 | ❌ Not used |
| 0x13 | GetChanges | "GetChanges" | 0x53 | ❌ We use 0x18! |
| 0x14 | MoreAvailable | "MoreAvailable" | 0x54 | ❌ Not used |
| 0x15 | WindowSize | "WindowSize" | 0x55 | ❌ We use 0x5F! |
| 0x16 | Commands | "Perform" | 0x56 | ❌ NEVER USED! |
| 0x17 | Options | "Options" | 0x57 | ❌ Not used |
| 0x18 | FilterType | "FilterType" | 0x58 | ❌ Not used |
| 0x19 | Truncation | "Truncation" | 0x59 | ❌ Not used |
| 0x1A | RtfTruncation | "RtfTruncation" | 0x5A | ❌ Not used |
| 0x1B | Conflict | "Conflict" | 0x5B | ❌ Not used |
| 0x1C | Collections | "Folders" | 0x5C | ❌ Not used |
| 0x1D | Data | "Data" | 0x5D | ❌ Not used |

---

## 🚨 CRITICAL ERRORS IN OUR IMPLEMENTATION

### What We're Using (WRONG!)

```python
# Current (WRONG):
Status: 0x49          # Should be 0x4E (0x0E + 0x40)
SyncKey: 0x4A         # Should be 0x4B (0x0B + 0x40) 
Collections: 0x46     # Should be 0x5C (0x1C + 0x40)
Collection: 0x47      # Should be 0x4F (0x0F + 0x40)
CollectionId: 0x48    # Should be 0x52 (0x12 + 0x40)
Commands: 0x4B        # Should be 0x56 (0x16 + 0x40)
Add: 0x4C             # Should be 0x47 (0x07 + 0x40)
ServerId: 0x4D        # CORRECT!
ApplicationData: 0x4E # NO SUCH TOKEN in AirSync!
```

### What Z-Push Uses (CORRECT!)

```php
// Z-Push tokens (AUTHORITATIVE):
0x05 => "Synchronize"    // Sync
0x07 => "Add"            // Add
0x0B => "SyncKey"        // SyncKey
0x0D => "ServerEntryId"  // ServerId
0x0E => "Status"         // Status
0x0F => "Folder"         // Collection
0x12 => "FolderId"       // CollectionId
0x13 => "GetChanges"     // GetChanges (0x13, not 0x18!)
0x14 => "MoreAvailable"  // MoreAvailable
0x15 => "WindowSize"     // WindowSize (0x15, not 0x1F!)
0x16 => "Perform"        // Commands
0x1C => "Folders"        // Collections
```

---

## ✅ CORRECTED TOKEN TABLE

| Element | Base (Z-Push) | With 0x40 | Previous (WRONG) |
|---------|---------------|-----------|------------------|
| Sync | 0x05 | 0x45 | 0x45 ✅ |
| Status | 0x0E | 0x4E | 0x49 ❌ |
| SyncKey | 0x0B | 0x4B | 0x4A ❌ |
| Collections | 0x1C | 0x5C | 0x46 ❌ |
| Collection | 0x0F | 0x4F | 0x47 ❌ |
| CollectionId | 0x12 | 0x52 | 0x48 ❌ |
| Commands | 0x16 | 0x56 | 0x4B ❌ |
| Add | 0x07 | 0x47 | 0x4C ❌ |
| ServerId | 0x0D | 0x4D | 0x4D ✅ |
| GetChanges | 0x13 | 0x13 (empty) | 0x18 ❌ |
| WindowSize | 0x15 | 0x55 | 0x5F ❌ |
| MoreAvailable | 0x14 | 0x54 | ❌ Missing |

---

## 📊 Impact Analysis

### Tokens We Got RIGHT
- Sync (0x45) ✅
- ServerId (0x4D) ✅

### Tokens We Got WRONG
- Status: Off by 5
- SyncKey: Off by 1
- Collections: Off by 22!
- Collection: Off by 8
- CollectionId: Off by 10
- Commands: Off by 11!
- Add: Off by 5
- GetChanges: Using wrong value entirely
- WindowSize: Off by 10

**Conclusion**: Almost EVERY token was wrong! This is why iPhone rejects our WBXML!

---

## Next Steps

1. ✅ Update `minimal_sync_wbxml.py` with Z-Push tokens
2. ✅ Test with iPhone
3. ✅ Document results
4. ✅ Rebuild Docker

**Source Authority**: Z-Push is the gold standard for ActiveSync WBXML

