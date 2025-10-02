# Email2 Token Verification

## From wbxml_encoder.py (AUTHORITATIVE)
```
"Subject": 0x0F       → 0x0F + 0x40 = 0x4F
"From": 0x10          → 0x10 + 0x40 = 0x50  ❌ BUT collides with Class!
"To": 0x11            → 0x11 + 0x40 = 0x51
"DateReceived": 0x12  → 0x12 + 0x40 = 0x52
"Importance": 0x15    → 0x15 + 0x40 = 0x55
"Read": 0x16          → 0x16 + 0x40 = 0x56  ✅ FIXED!
"MessageClass": 0x1C  → 0x1C + 0x40 = 0x5C
```

## Current Implementation in minimal_sync_wbxml.py

Line 176-181: From = 0x44  
**WRONG!** Should be 0x50 (but collides with Class)

Line 183-191: Subject = 0x45  
**WRONG!** Should be 0x4F

Line 193-201: DateReceived = 0x4F
**WRONG!** Should be 0x52

Line 203-214: To = 0x43
**WRONG!** Should be 0x51

Line 216-223: Read = 0x56 ✅ CORRECT (after fix)

Line 225-229: MessageClass = 0x5A
**WRONG!** Should be 0x5C

Line 231-236: Importance = 0x46
**WRONG!** Should be 0x55

## MASSIVE TOKEN ERRORS!

ALL Email2 tokens are WRONG except Read!

### The Real Problem
wbxml_encoder.py has different token mapping than what we're using!

We've been using tokens from a DIFFERENT source or making them up!

### Solution
Use wbxml_encoder.py as AUTHORITATIVE source for Email2 tokens!
