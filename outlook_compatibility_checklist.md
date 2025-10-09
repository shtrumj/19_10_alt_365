# Outlook ActiveSync Compatibility Checklist

## Comparison: Our Implementation vs Z-Push/Grommunio Best Practices

### ✅ WBXML Structure (VERIFIED COMPLIANT)

- [x] Top-level `<Status>1</Status>` under `<Sync>`
- [x] Collection-level `<Status>1</Status>` under `<Collection>`
- [x] Element order: SyncKey → CollectionId → Status → Class → Commands
- [x] Proper codepage switching (AirSync → Email → AirSyncBase → AirSync)
- [x] `<Class>Email</Class>` present
- [x] `<Commands>` wrapping `<Add>` elements
- [x] AirSyncBase `<Body>` structure: Type → EstimatedDataSize → Truncated → Data → ContentType
- [x] `<NativeBodyType>` present after `<Body>`

### ⚠️ POTENTIAL ISSUES (Needs Investigation)

#### 1. Body Type Selection

**Our Implementation:**

- Sending `Type=1` (PlainText) with 512-byte truncation
- ContentType: `text/plain; charset=utf-8`

**Z-Push/Grommunio Known Behavior:**

- Prefer `Type=2` (HTML) for better Outlook compatibility
- Outlook may reject PlainText-only responses
- **ACTION**: Try sending HTML bodies (Type=2) instead

#### 2. Truncation Strategy

**Our Implementation:**

- First sync: 512 bytes per email
- Max window: 3 emails
- Total response: ~1300 bytes

**Z-Push/Grommunio Best Practices:**

- No truncation on first sync (or much larger like 200KB)
- Let Outlook request truncation if needed
- **ACTION**: Try NO truncation (send full bodies)

#### 3. EstimatedDataSize Accuracy

**Our Implementation:**

- EstimatedDataSize: "188" or "201" bytes
- Actual truncated data: 512 bytes (character-based, so ~170 bytes after UTF-8 encoding)
- **ISSUE**: EstimatedDataSize doesn't match actual data size!

**MS-ASCMD Requirement:**

- EstimatedDataSize MUST be the size of the FULL (untruncated) body
- **ACTION**: Fix EstimatedDataSize to reflect original body size, not truncated size

#### 4. WindowSize Handling

**Our Implementation:**

- Capping client's WindowSize=512 down to 3

**Z-Push/Grommunio:**

- Respect client's WindowSize (within reason, cap at 25-100)
- **ACTION**: Increase MAX_WINDOW_SIZE to 25

#### 5. Empty Initial Response

**Our Implementation:**

- Currently DISABLED (outlook_needs_empty = False)
- Sending data immediately on Sync 0→1

**Z-Push/Grommunio:**

- Some implementations send empty response on 0→1 for Outlook
- Others send data immediately
- **ACTION**: This is inconsistent across implementations

#### 6. MIMESupport Flag

**Our Implementation:**

- Not sending `<AirSyncBase:MIMESupport>` in responses

**Outlook Requirement:**

- Outlook may expect `<MIMESupport>` to indicate MIME capabilities
- Values: 0=Never, 1=SMIME only, 2=All MIME
- **ACTION**: Add `<MIMESupport>2</MIMESupport>` to responses

#### 7. MessageClass Validation

**Our Implementation:**

- Always sending `MessageClass=IPM.Note`

**Outlook:**

- Strictly validates MessageClass
- **STATUS**: This should be fine

#### 8. Body Preview vs Full Body

**Our Implementation:**

- Sending truncated body with Truncated=1

**Outlook Behavior:**

- May ignore truncated bodies entirely
- May require BodyPart for previews instead of Body
- **ACTION**: Consider sending full bodies without truncation

### 🔬 EXPERIMENTS TO TRY (In Order)

#### Experiment 1: Fix EstimatedDataSize Bug

**Current:** EstimatedDataSize reflects truncated size
**Fix:** EstimatedDataSize must be FULL original body size
**Priority:** CRITICAL - This violates MS-ASCMD spec!

#### Experiment 2: Send HTML Instead of PlainText

**Current:** Type=1 (PlainText)
**Fix:** Type=2 (HTML)
**Reason:** Outlook prefers HTML bodies

#### Experiment 3: Remove Truncation Entirely

**Current:** 512-byte truncation
**Fix:** Send full email bodies (no truncation)
**Reason:** Outlook may reject truncated bodies on initial sync

#### Experiment 4: Add MIMESupport Element

**Current:** Not sending
**Fix:** Add `<AirSyncBase:MIMESupport>2</MIMESupport>`
**Reason:** Outlook may expect this

#### Experiment 5: Increase WindowSize

**Current:** Max 3 emails
**Fix:** Max 25 emails
**Reason:** Sending too few may confuse Outlook

### 📊 Z-Push/Grommunio Documented Differences

Based on available documentation:

1. **Grommunio** explicitly states:
   - Prefers MAPI/HTTP for Outlook Desktop
   - ActiveSync for Outlook has "limited feature support"
   - Suggests avoiding ActiveSync for Outlook Desktop

2. **Z-Push** known patterns:
   - Sends HTML bodies by default
   - Uses larger WindowSize (25-100)
   - No aggressive truncation on first sync
   - Properly calculates EstimatedDataSize

### 🎯 MOST LIKELY ROOT CAUSE

**EstimatedDataSize Bug** is the most likely culprit:

- We're sending EstimatedDataSize="188"
- But the actual truncated body is ~170 bytes
- This doesn't match and violates MS-ASCMD
- Outlook may silently reject responses with incorrect EstimatedDataSize

**Second Most Likely:**

- Sending PlainText (Type=1) instead of HTML (Type=2)
- Outlook Desktop strongly prefers HTML bodies
