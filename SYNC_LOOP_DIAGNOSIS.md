# Sync Loop Diagnosis - iOS Rejection of Truncated Bodies

**Date**: October 11, 2025  
**Status**: 🔍 DIAGNOSED  
**Impact**: iOS Mail sync loop - CRITICAL

---

## What's Actually Happening

### Sequence of Events (from activesync.log):

1. **First Sync** (07:29:26):
   - iOS requests `truncation_size: 500` ✓
   - Server truncates correctly ✓
   - Server sends 4KB response with 5 emails ✓
   - Preview skipped correctly ✓
   - OPAQUE encoding used ✓

2. **Ping Command** (07:29:33):
   - iOS enters Ping mode (waiting for changes)
   - This is normal behavior ✓

3. **Second Sync - iOS SWITCHES** (07:29:34):
   - iOS requests `truncation_size: 32768` ❌
   - Server sends FULL bodies (91KB response) ❌
   - iOS overwhelmed, fails ❌

4. **Loop Continues**:
   - iOS keeps requesting with 32KB
   - Server keeps sending 91KB-280KB responses
   - iOS never displays emails

---

## The Question

**Why does iOS switch from 500 to 32768?**

iOS only does this when it's **unable to use** the truncated bodies from the first sync. Possible reasons:

### 1. Emails Not Displaying

- iOS receives truncated bodies
- Tries to render them in Mail app
- Rendering fails (OPAQUE encoding issue?)
- iOS gives up on truncation, requests full bodies

### 2. Response Format Issue

- Truncated bodies are correct
- But metadata or structure is wrong
- iOS can't process the email list
- Retries with full bodies hoping to fix it

### 3. Client State Issue

- First sync completes
- iOS commits to database
- But something in the commit fails
- iOS resets and requests full sync

---

## Evidence from Logs

### First Sync (GOOD):

```json
Line 33: {"truncation_size": 500, "effective_truncation": 500}
Line 48: {"preview_skipped", "is_truncated": "1"}
Line 64: {"encoding": "opaque_utf8", "data_length": 429}
Line 86: {"content_length": 4004}  ← 4KB response, perfect!
```

### Second Sync (BAD):

```json
Line 264: "body_preview": "...G\x0032768..."  ← CLIENT switched!
Line 266: {"truncation_size": 32768}
Line 273: {"truncation_size_param": 32768}
Line 276: {"will_truncate": false}
Line 319: {"content_length": 91139}  ← 91KB response, overwhelming!
```

---

## Possible Root Causes

### Theory 1: OPAQUE Encoding Not Working Properly

**Status**: Needs testing on device

We fixed the OPAQUE encoding, but the fix hasn't been tested on an actual iOS device yet. If the OPAQUE encoding is still wrong, iOS would:

1. Receive truncated bodies
2. Try to decode OPAQUE data
3. Fail to decode or render
4. Give up, request full bodies

**Test**: Delete account, re-add, check if emails appear in Mail app after first sync.

### Theory 2: EstimatedDataSize Mismatch

**Status**: Log shows compliant

The logs show `"ms_asairs_compliant": true`, but we should verify:

- `EstimatedDataSize` = full body size (20668)
- Actual `Data` length = truncated size (429)
- iOS expects this for truncated bodies

**Test**: Check if iOS is rejecting responses due to size mismatch.

### Theory 3: Missing Metadata

**Status**: Unlikely

All required fields are present:

- Subject ✓
- From ✓
- To ✓
- DateReceived ✓
- MessageClass ✓

**Test**: Compare our response with working ActiveSync servers.

---

## The Fix Strategy

### Immediate Action:

**TEST ON DEVICE** - The logs show our server is doing everything correctly for the first sync. We need to see what happens on the iOS device:

1. **Delete the account** from iOS Settings → Mail
2. **Clear the log**: `echo "" > logs/activesync/activesync.log`
3. **Re-add the account** on iOS
4. **Check Mail app immediately**:
   - Do emails appear in the list?
   - Can you read the subjects?
   - Can you see previews?
   - What happens when you tap an email?

### If Emails DON'T Appear:

The OPAQUE encoding fix may need adjustment. Check:

- Are we encoding UTF-8 correctly?
- Is the OPAQUE length calculation correct?
- Does iOS expect different encoding for truncated vs full bodies?

### If Emails Appear But Don't Open:

The rendering issue is in the full body fetch, not the truncated preview. Check:

- Full body OPAQUE encoding
- HTML structure
- Charset handling

---

## Current Status

**Server Behavior**: ✅ CORRECT for first sync

- Truncates to 500 bytes
- Skips Preview
- Uses OPAQUE encoding
- Sends small 4KB response

**Client Behavior**: ❌ REJECTS and retries

- Receives 4KB response
- Switches to 32KB request
- Indicates first sync failed somehow

**Next Step**: **DEVICE TESTING** required to see actual iOS Mail behavior

---

## Hypothesis

The OPAQUE encoding fix is syntactically correct but may not be producing the exact byte sequence iOS expects. iOS is very strict about ActiveSync protocol compliance, and even small deviations cause it to reject responses and fall back to requesting full bodies.

**We need to test on device to confirm whether:**

1. Emails appear in Mail app after first sync (opaque encoding working)
2. Emails can be opened and read (full body fetch working)
3. Or if iOS immediately rejects and requests full bodies (encoding still wrong)

Without device testing, we're debugging blind. The logs show our server is technically correct, but iOS is rejecting it for some reason we can't see in logs alone.
