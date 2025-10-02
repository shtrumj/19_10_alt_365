# ✅ Verified Facts vs ❓ Assumptions - ActiveSync Analysis

**Date**: October 2, 2025  
**Purpose**: Clearly separate what we KNOW works vs what we THINK might be the problem

---

## ✅ VERIFIED FACTS (100% Confirmed)

### Working FolderSync Command
1. ✅ **FolderSync succeeds** - iPhone accepts and displays all folders
2. ✅ **WBXML structure is valid** - iPhone parses it correctly
3. ✅ **Authentication works** - Basic Auth accepted
4. ✅ **HTTP transport works** - Requests/responses flow correctly
5. ✅ **SyncKey="1" works for FolderSync** - Simple integer accepted
6. ✅ **170-byte WBXML accepted** - Size is not an issue
7. ✅ **Folder data sent immediately** - FolderSync sends 6 folders with SyncKey 0→1
8. ✅ **Codepage switching works** - FolderHierarchy namespace handled correctly

### Failing Sync Command
9. ✅ **Sync ALWAYS fails** - 0% success rate across all attempts
10. ✅ **iPhone stuck at SyncKey="0"** - Never progresses to SyncKey="1"
11. ✅ **iPhone sends Ping commands** - Trying to maintain connection (900s heartbeat)
12. ✅ **CollectionId="1" requested** - iPhone requests Inbox sync
13. ✅ **WindowSize=1** requested - iPhone wants 1 email at a time (initially)
14. ✅ **Server finds 19 emails** - Data is available
15. ✅ **WBXML generated successfully** - No Python errors

### WBXML Token Values (Verified Against Grommunio)
16. ✅ **Sync token: 0x45** (0x05 + 0x40 content flag)
17. ✅ **Status token: 0x4E** (0x0E + 0x40)
18. ✅ **SyncKey token: 0x4B** (0x0B + 0x40)
19. ✅ **Collections token: 0x5C** (0x1C + 0x40)
20. ✅ **Collection token: 0x4F** (0x0F + 0x40)
21. ✅ **CollectionId token: 0x52** (0x12 + 0x40)

### iPhone Request Details (Verified from Logs)
22. ✅ **User-Agent**: "Apple-iPhone16C2/2301.341"
23. ✅ **Protocol Version**: AS 14.1
24. ✅ **Device ID**: KO090MSD656QV68VR4UUD92RA4
25. ✅ **Request body preview**: Contains valid WBXML with SyncKey="0"

---

## ❓ ASSUMPTIONS (Not Yet Verified)

### About WBXML Structure
1. ❓ **Element ordering correct** - Matches Grommunio but not byte-for-byte verified
2. ❓ **All mandatory fields present** - Based on docs, not actual Exchange capture
3. ❓ **Codepage switches correct** - Seems right but not confirmed against real Exchange
4. ❓ **String encoding correct** - UTF-8 assumed, not verified
5. ❓ **END tags correct** - Placement based on docs, not real traffic

### About Initial Sync Flow
6. ❓ **Empty initial sync correct** - Based on Grommunio code, but FolderSync sends data!
7. ❓ **No Commands block correct** - Grommunio pattern, but might be wrong interpretation
8. ❓ **SyncKey 0→1 transition** - Assumed based on docs, not verified with real server

### About Email Data Structure
9. ❓ **Email fields complete** - We include Subject, From, To, Body, but maybe missing required fields?
10. ❓ **ServerId format correct** - Using simple integers "1", "2", "3"...
11. ❓ **MessageClass correct** - Using "IPM.Note"
12. ❓ **Body encoding correct** - Using plain text with Type=1

### About Protocol Compatibility
13. ❓ **AS 14.1 fully supported** - We claim 14.1 but might have gaps
14. ❓ **iPhone-specific requirements** - May have undocumented requirements
15. ❓ **Namespace handling** - AirSync vs FolderHierarchy might need different treatment

---

## 🔬 EXPERIMENTS COMPLETED

### Test 1: Empty Initial Sync
- **Size**: 37 bytes
- **Content**: No emails, no Commands block
- **Result**: ❌ FAILED
- **Conclusion**: Empty sync is NOT the issue

### Test 2: UUID SyncKeys
- **Size**: 113 bytes  
- **Format**: `{1fddbfd9-f320-4b2f-b68c-bd757523bce5}1`
- **Result**: ❌ FAILED
- **Conclusion**: UUID format is NOT required

### Test 3: Simple Integer SyncKeys
- **Size**: 37 bytes (empty) 
- **Format**: "1"
- **Result**: ❌ FAILED
- **Conclusion**: Simple format is correct but not the issue

### Test 4: Send Emails Immediately
- **Size**: 864 bytes
- **Content**: 19 emails with full data
- **Result**: ❌ FAILED
- **Conclusion**: Sending data immediately is NOT the solution

---

## 🎯 CRITICAL UNKNOWN

**What is fundamentally different between FolderSync and Sync that makes one work and the other fail?**

Possibilities:
1. Different WBXML encoding rules for different namespaces
2. Missing mandatory element we haven't identified
3. Wrong codepage sequence
4. iPhone expecting different protocol flow
5. Bug in our WBXML encoder for Sync specifically

---

## 🔍 WHAT WE NEED TO VERIFY

### Priority 1: Get Real Exchange WBXML
- **Action**: Packet capture from iPhone → real Exchange Server
- **Why**: See EXACT byte sequence that works
- **How**: Wireshark/tcpdump, SSL interception

### Priority 2: Test with Different Client
- **Action**: Try Android phone or Outlook  
- **Why**: Determine if iPhone-specific or general issue
- **How**: Connect Android device to our server

### Priority 3: Byte-by-Byte WBXML Comparison
- **Action**: Compare our Sync WBXML vs working FolderSync WBXML
- **Why**: Find subtle differences in encoding
- **How**: Hex dump analysis, focus on structure differences

### Priority 4: Read MS-ASCMD Spec Cover-to-Cover
- **Action**: Deep dive into Sync command section
- **Why**: Find requirements we missed
- **How**: Read spec with focus on "MUST" requirements

---

## 📊 Confidence Levels

| Item | Confidence | Reason |
|------|-----------|---------|
| FolderSync works | 100% | Proven in logs |
| Sync fails | 100% | Consistent failure |
| Token values correct | 95% | Verified against Grommunio |
| Element order correct | 70% | Matches docs but not verified |
| All fields present | 60% | Based on docs, not confirmed |
| Protocol flow correct | 50% | Assumed from Grommunio |
| No missing requirements | 30% | Can't prove negative |

---

## 💡 NEXT STEP: Real-World Verification

**We need to STOP assuming and START verifying against real working implementations!**

1. Capture traffic from real Exchange
2. Compare byte-for-byte
3. Fix differences
4. Test iteratively

Until we have real Exchange WBXML to compare against, we're shooting in the dark.

