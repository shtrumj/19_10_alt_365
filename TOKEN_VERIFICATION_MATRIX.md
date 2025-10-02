# 🔍 WBXML Token Verification Matrix

**Methodology**: Compare token values from ALL sources, use statistical majority + recency weighting

---

## Sources Compared

1. **wbxml_encoder.py** (our reference, unknown provenance)
2. **decode_sync_wbxml.py** (created during debugging)
3. **activesync.md** (documentation, claimed from Z-Push)
4. **wbxml_encoder_v2.py** (attempt to match Grommunio)

---

## Token Comparison Table (AirSync Codepage 0)

| Element | wbxml_encoder.py | decode_sync_wbxml.py | activesync.md | wbxml_encoder_v2.py | **MAJORITY** |
|---------|------------------|----------------------|---------------|---------------------|--------------|
| **Sync** | 0x05 | 0x05 | 0x05 | 0x05 | ✅ **0x05** (4/4) |
| **Status** | 0x09 | 0x0C | 0x0C | 0x09 | ⚠️ **0x0C** (2/4) TIE! |
| **SyncKey** | 0x0A | 0x20 | 0x0B | 0x0A | ⚠️ **0x0A** (2/4) vs 0x20,0x0B |
| **Collections** | 0x06 | ❌ | 0x0F | 0x06 | ⚠️ **0x06** (2/3) vs 0x0F |
| **Collection** | 0x07 | 0x0D | 0x0E | 0x07 | ⚠️ **0x07** (2/4) vs 0x0D,0x0E |
| **CollectionId** | 0x08 | 0x11 | 0x11 | 0x08 | ⚠️ **TIE**: 0x08 (2/4) vs 0x11 (2/4) |
| **Commands** | 0x0B | 0x12 | 0x12 | 0x0B | ⚠️ **TIE**: 0x0B (2/4) vs 0x12 (2/4) |
| **Add** | 0x0C | 0x0F | 0x07 | ❌ | ❌ **NO CONSENSUS** |
| **ServerId** | 0x0D | 0x0E | 0x08 | ❌ | ❌ **NO CONSENSUS** |
| **GetChanges** | ❌ | 0x18 | 0x18 | ❌ | ✅ **0x18** (2/2) |
| **WindowSize** | ❌ | 0x1F | 0x1F | ❌ | ✅ **0x1F** (2/2) |

---

## Critical Findings

### ⚠️ NO CONSENSUS ON CRITICAL TOKENS!

**We have NO authoritative source!** Each source contradicts the others.

### Recency Analysis

- **wbxml_encoder.py**: Unknown age, unknown source
- **decode_sync_wbxml.py**: Created ~2025-09-29 during debugging
- **activesync.md**: Updated 2025-10-02, claims Z-Push source
- **wbxml_encoder_v2.py**: Created ~2025-09-29, attempts Grommunio match

**Recency weight doesn't help - all recent!**

---

## The REAL Problem

**WE DON'T HAVE THE GROUND TRUTH!**

All our sources are:
1. Self-created during debugging
2. Copied from unknown sources
3. Not verified against Microsoft specification
4. Not verified against working implementation

---

## Required Action

### 1. Get Microsoft MS-ASWBXML Specification

**MUST** download the official PDF from Microsoft:
- Search: "MS-ASWBXML site:microsoft.com"
- Get token tables directly from spec
- This is THE authoritative source

### 2. Extract Z-Push Token Definitions

**MUST** get wbxmldefs.php from Z-Push:
```bash
wget https://raw.githubusercontent.com/Z-Hub/Z-Push/master/src/lib/wbxml/wbxmldefs.php
grep -A 50 "SYNC_" wbxmldefs.php
```

### 3. Extract Grommunio-Sync Token Definitions

**MUST** get from Grommunio-Sync:
```bash
wget https://raw.githubusercontent.com/grommunio/grommunio-sync/master/lib/wbxml/wbxmldefs.php
grep -A 50 "SYNC_" wbxmldefs.php
```

### 4. Statistical Resolution

Once we have ALL THREE authoritative sources:
- Microsoft: Weight 40% (specification)
- Grommunio-Sync: Weight 35% (recent, maintained)
- Z-Push: Weight 25% (older, but proven)

Use weighted majority voting for each token.

---

## Immediate Action Plan

**STOP coding blind!**

1. Download official sources
2. Create authoritative token table
3. Update minimal_sync_wbxml.py with VERIFIED tokens
4. Test
5. Document evidence basis for each token

**Status**: Currently using UNVERIFIED tokens from unknown sources!

