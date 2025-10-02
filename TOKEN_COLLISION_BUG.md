# 🚨 CRITICAL BUG: WBXML Token Collision

**Date**: October 2, 2025  
**Severity**: CRITICAL  
**Impact**: Commands block uses wrong token, colliding with SyncKey!

---

## The Bug

In `minimal_sync_wbxml.py` line 148 (before fix):
```python
output.write(b'\x52')  # Commands with content
```

**Problem**: `0x52` is **CollectionId** (0x12 + 0x40), NOT Commands!

## Attempted Fix Had Another Bug!

Changed to:
```python
output.write(b'\x4B')  # Commands with content
```

**Problem**: `0x4B` is **SyncKey** (0x0A + 0x40), NOT Commands!

## Root Cause: Conflicting Token Maps

### Source 1: `wbxml_encoder.py` (lines 60-62)
```python
"SyncKey": 0x0A,      # 0x0A + 0x40 = 0x4A
"Commands": 0x0B,     # 0x0B + 0x40 = 0x4B
```

### Source 2: `minimal_sync_wbxml.py` (our actual implementation)
```python
# SyncKey (0x0B + 0x40 = 0x4B)  ← WRONG! Should be 0x0A!
output.write(b'\x4B')  

# Commands (0x12 + 0x40 = 0x52)  ← WRONG! Should be 0x0B!
output.write(b'\x52')
```

### Source 3: `activesync.md` (documentation)
```
- SyncKey: 0x0B + 0x40 = 0x4B  ← CONFLICT!
- Commands: 0x12 + 0x40 = 0x52  ← CONFLICT!
```

## Correct Tokens (from wbxml_encoder.py)

**AirSync Namespace (codepage 0):**
| Element | Base | +0x40 | Hex |
|---------|------|-------|-----|
| Sync | 0x05 | = 0x45 | ✅ |
| Collections | 0x06 | = 0x46 | ❓ |
| Collection | 0x07 | = 0x47 | ❓ |
| CollectionId | 0x08 | = 0x48 | ❓ |
| Status | 0x09 | = 0x49 | ❓ |
| **SyncKey** | **0x0A** | **= 0x4A** | ❌ WRONG in code! |
| **Commands** | **0x0B** | **= 0x4B** | ❌ WRONG in code! |
| **Add** | **0x0C** | **= 0x4C** | ❌ WRONG in code! |
| **ServerId** | **0x0D** | **= 0x4D** | ❌ WRONG in code! |
| **ApplicationData** | **0x0E** | **= 0x4E** | ❌ WRONG in code! |

## What We're Actually Using (WRONG!)

Based on `minimal_sync_wbxml.py`:
- SyncKey: 0x4B (should be 0x4A)
- Collections: 0x5C (should be 0x46)
- Collection: 0x4F (should be 0x47)
- CollectionId: 0x52 (should be 0x48)
- Status: 0x4E (should be 0x49)
- Add: 0x47 (should be 0x4C)
- ServerId: 0x48 (should be 0x4D)
- ApplicationData: 0x49 (should be 0x4E)

## Impact

**EVERY SINGLE TOKEN IS WRONG!!!**

This explains why iPhone rejects our Sync responses - we're sending completely invalid WBXML!

## The Real Question

**Where did the wrong tokens come from?**

Looking at the pattern in `minimal_sync_wbxml.py`:
- Claims to be "per Grommunio wbxmldefs.php"
- But doesn't match `wbxml_encoder.py` at all!
- Off by different amounts for each token

**Hypothesis**: The tokens in `minimal_sync_wbxml.py` were taken from a DIFFERENT namespace or codepage!

## Urgent Fix Needed

1. **Stop everything**
2. **Get authoritative token list** from Microsoft MS-ASWBXML spec
3. **Rewrite `minimal_sync_wbxml.py`** with correct tokens
4. **Test immediately**

This is likely THE root cause of all failures!

