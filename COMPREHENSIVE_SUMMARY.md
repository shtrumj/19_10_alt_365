# 📋 iPhone ActiveSync Sync Failure - Comprehensive Analysis

**Date**: October 2, 2025  
**Status**: ❌ UNRESOLVED - iPhone stuck at SyncKey="0" loop  
**FolderSync**: ✅ WORKS  
**Sync (Email)**: ❌ FAILS  

---

## 🎯 What Works

### FolderSync Command
- **Result**: ✅ **100% SUCCESS**
- **SyncKey Format**: Simple integer "1"
- **WBXML Size**: 170 bytes
- **Data Sent**: 6 folders immediately on initial sync
- **iPhone Behavior**: Accepts immediately, displays all folders

---

## ❌ What Doesn't Work

### Sync Command (Email)
- **Result**: ❌ **0% SUCCESS - INFINITE LOOP**
- **iPhone Behavior**: Continuously sends SyncKey="0", never progresses
- **All Attempts Failed**: See below

---

## 🔬 All Attempts Made

### Attempt 1: Correct WBXML Tokens ✅
- **Action**: Fixed all token values per Z-Push/Grommunio
- **Result**: ❌ Still rejected

### Attempt 2: Empty Initial Sync (37 bytes) ✅
- **Action**: Send NO emails on SyncKey 0→1 (like Grommunio pattern)
- **WBXML**: 37 bytes
- **Result**: ❌ Still rejected

### Attempt 3: UUID-Based SyncKeys (113 bytes) ✅
- **Action**: Implement `{UUID}Counter` format from Grommunio
- **WBXML**: 113 bytes
- **SyncKey**: `{1fddbfd9-f320-4b2f-b68c-bd757523bce5}1`
- **Result**: ❌ Still rejected

### Attempt 4: Revert to Simple Integer ✅
- **Action**: Use simple "1" like FolderSync
- **WBXML**: 37 bytes (empty sync)
- **Result**: ❌ Still rejected

### Attempt 5: Send Emails Immediately (864 bytes) ✅
- **Action**: Send 19 emails with SyncKey 0→1 (like FolderSync sends folders)
- **WBXML**: 864 bytes
- **Result**: ❌ Still rejected

---

## 📊 Test Matrix

| Test | SyncKey | Size | Emails | Result |
|------|---------|------|--------|--------|
| FolderSync | "1" | 170 bytes | N/A (folders) | ✅ WORKS |
| Sync (empty) | "1" | 37 bytes | 0 | ❌ FAILS |
| Sync (UUID) | "{uuid}1" | 113 bytes | 0 | ❌ FAILS |
| Sync (simple) | "1" | 37 bytes | 0 | ❌ FAILS |
| Sync (with data) | "1" | 864 bytes | 19 | ❌ FAILS |

---

## ✅ What's Verified Correct

1. **WBXML Header**: `03016a000000` (matches FolderSync)
2. **Codepage Switching**: `0x00 0x00` for AirSync (matches FolderSync)
3. **Token Values**: All verified against Z-Push wbxmldefs.php
4. **Element Ordering**: Matches Grommunio-Sync exactly
5. **SyncKey Format**: Simple integer (matches FolderSync)
6. **HTTP Headers**: Same as working FolderSync
7. **Authentication**: Works (FolderSync succeeds)
8. **Database State**: Properly managed

---

## 🤔 What Could Be Wrong?

### Theory 1: Codepage Issue
- FolderSync uses FolderHierarchy namespace
- Sync uses AirSync namespace
- **Maybe different codepage handling?**

### Theory 2: iPhone-Specific Variant
- iPhone might use proprietary ActiveSync variant
- **Not documented in MS-ASCMD spec**

### Theory 3: Required But Undocumented Element
- Some element required for Sync but not FolderSync
- **Not in Microsoft spec or Grommunio code**

### Theory 4: Protocol Version Issue
- iPhone sends `MS-ASProtocolVersion: 14.1`
- **Maybe our Sync response doesn't match 14.1 spec?**

### Theory 5: ServerId Format
- FolderSync ServerIds: "1", "2", "3"...
- Sync ServerIds: "1", "2", "3"...
- **Maybe Sync needs different format?**

---

## 🔍 What We Haven't Tried

1. **Packet Capture from Real Exchange Server**
   - Compare byte-for-byte with our implementation
   - See actual Exchange Sync WBXML structure

2. **Test with Different ActiveSync Client**
   - Android phone
   - Windows Outlook
   - **Isolate if iPhone-specific**

3. **Different Protocol Version**
   - Try AS 12.1 instead of 14.1
   - **Maybe 14.1 has undocumented requirements**

4. **Different HTTP Headers**
   - MS-Server-ActiveSync version
   - Additional ActiveSync-specific headers

5. **Raw WBXML from Grommunio-Sync**
   - Install real Grommunio server
   - Capture its Sync WBXML
   - Compare with ours byte-for-byte

---

## 💡 Recommended Next Steps

### Immediate (< 1 day)
1. **Packet capture from real Exchange + iPhone**
   - Set up tcpdump/Wireshark
   - Capture actual working Sync session
   - Compare WBXML byte-by-byte

2. **Test with Android phone**
   - Verify if our Sync works on Android
   - Isolate iPhone vs general issue

### Short-term (1-3 days)
3. **Install real Grommunio-Sync**
   - Run it in Docker
   - Connect iPhone to it
   - Capture working WBXML

4. **Deep dive into MS-ASCMD 14.1 spec**
   - Read entire Sync command section
   - Look for iPhone-specific notes

### Medium-term (1 week)
5. **Engage ActiveSync community**
   - Z-Push forums
   - Grommunio community
   - Microsoft forums

6. **Consider professional Exchange consultation**
   - Hire ActiveSync expert
   - Get direct guidance

---

## 📈 Success Metrics

- **Current**: FolderSync 100%, Sync 0%
- **Target**: Both at 100%
- **Blocker**: Unknown protocol incompatibility

---

## 🎓 Lessons Learned

1. ✅ **Token values matter** - Had to fix many incorrect tokens
2. ✅ **Element ordering matters** - Grommunio has specific order
3. ✅ **Initial sync is special** - Different structure than regular sync
4. ❌ **But none of this solved the problem!**

---

## 🔥 The Core Mystery

**Why does FolderSync work but Sync doesn't?**

They use:
- Same WBXML version
- Same charset
- Same authentication
- Same HTTP transport
- Same overall structure
- Same synckey format

**Yet one works, one doesn't!**

This suggests a **fundamental protocol-level difference** between FolderHierarchy and AirSync namespaces that we haven't identified.

---

## 📞 Request for Help

If you're reading this and have ActiveSync experience:

1. Have you seen this before?
2. Do you know what we're missing?
3. Can you provide a working Sync WBXML hex dump?
4. Is there iPhone-specific documentation?

**Contact**: [Add your contact info]

---

**End of Analysis**
