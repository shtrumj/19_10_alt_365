# Expert Diagnosis: Protocol Version Negotiation Issue

## 🐛 THE PROBLEM

iPhone keeps looping "resend pending... SAME key" and never downloads mail because:

### 1. **Version Mismatch (CRITICAL!)**
```python
# Current _eas_headers():
"MS-ASProtocolVersion": "14.1",                      # ← We echo 14.1
"MS-ASProtocolVersions": "12.1,14.0,14.1,16.0,16.1"  # ← But advertise 16.1!
```

**What happens:**
- iOS sees `MS-ASProtocolVersions: ...16.1` on OPTIONS
- iOS picks the **highest** version: `16.1`
- iOS sends `MS-ASProtocolVersion: 16.1` on POST requests
- **We ignore it** and send back `14.1` format WBXML
- iOS rejects the response as invalid for 16.1 → loops at SyncKey=0!

### 2. **OPTIONS vs Command Response Headers**
```python
# OPTIONS should have:
MS-ASProtocolVersions: "14.1"       # List of supported versions
MS-ASProtocolCommands: "Sync,..."   # List of commands
# NO MS-ASProtocolVersion (singular)!

# POST responses should have:
MS-ASProtocolVersion: "14.1"        # Echo the NEGOTIATED version
# Can include MS-ASProtocolVersions too, but not required
```

**Our current code:** Same headers for both! ❌

### 3. **Not Echoing Client's Requested Version**
We hardcode `14.1` instead of reading what the client sent:
```python
# We should do this:
ms_ver = request.headers.get("MS-ASProtocolVersion", "14.1")
headers["MS-ASProtocolVersion"] = ms_ver  # Echo it back!
```

## ✅ THE FIX

### FIX #31: Protocol Version Negotiation

#### A) Cap advertised versions to 14.1 only (for now)
```python
def _eas_headers(policy_key: str = None, protocol_version: str = None) -> dict:
    """Headers for ActiveSync command responses."""
    headers = {
        "MS-Server-ActiveSync": "15.0",
        "Content-Type": "application/vnd.ms-sync.wbxml",
        # ... cache/pragma headers ...
        
        # Echo the negotiated version (required on POST responses)
        "MS-ASProtocolVersion": protocol_version or "14.1",
        
        # We CAN include the list, but it's optional on POST responses
        "MS-ASProtocolVersions": "14.1",  # ← CAP TO 14.1 while debugging!
        
        "MS-ASProtocolCommands": "...",
    }
    if policy_key:
        headers["X-MS-PolicyKey"] = policy_key
    return headers
```

#### B) Separate OPTIONS headers
```python
def _eas_options_headers() -> dict:
    """Headers for OPTIONS discovery only."""
    return {
        "MS-Server-ActiveSync": "15.0",
        "Allow": "OPTIONS,POST",
        "Cache-Control": "private, no-cache",
        "Pragma": "no-cache",
        
        # OPTIONS advertises list of versions (plural)
        "MS-ASProtocolVersions": "14.1",  # ← CAP TO 14.1!
        
        # OPTIONS includes commands list
        "MS-ASProtocolCommands": (
            "Sync,FolderSync,Provision,Options,GetItemEstimate,Ping,"
            "ItemOperations,SendMail,SmartForward,SmartReply"
        ),
        
        # NO singular MS-ASProtocolVersion on OPTIONS!
    }
```

#### C) Echo client's version on every POST response
```python
# In Sync, FolderSync, Provision handlers:
client_version = request.headers.get("MS-ASProtocolVersion", "14.1")

# Validate it's one we support
if client_version not in ["12.1", "14.0", "14.1"]:
    client_version = "14.1"  # Fallback

headers = _eas_headers(
    policy_key=state.policy_key,
    protocol_version=client_version  # ← Echo back!
)
```

## 📊 VERIFICATION CHECKLIST

After implementing FIX #31, check logs for:

```
✅ OPTIONS:
   Request: GET ?Cmd=Options
   Response Headers:
     MS-ASProtocolVersions: 14.1
     MS-ASProtocolCommands: Sync,FolderSync,...
     NO MS-ASProtocolVersion (singular)

✅ Provision:
   Request: POST ?Cmd=Provision
     MS-ASProtocolVersion: 14.1 (from iPhone)
   Response Headers:
     MS-ASProtocolVersion: 14.1 (echo back)
     MS-ASProtocolVersions: 14.1 (optional)

✅ FolderSync:
   Request: POST ?Cmd=FolderSync
     MS-ASProtocolVersion: 14.1
   Response Headers:
     MS-ASProtocolVersion: 14.1 (echo back)

✅ Sync (initial):
   Request: POST ?Cmd=Sync, SyncKey=0
     MS-ASProtocolVersion: 14.1
   Response Headers:
     MS-ASProtocolVersion: 14.1 (echo back)
   Response Body: WBXML with SyncKey=1

✅ Sync (with items):
   Request: POST ?Cmd=Sync, SyncKey=1
     MS-ASProtocolVersion: 14.1
   Response Headers:
     MS-ASProtocolVersion: 14.1 (echo back)
   Response Body: WBXML with items, SyncKey=2
   
   ⚠️ KEY INDICATOR:
   Next request should have SyncKey=2!
   If iPhone still sends SyncKey=0, response is being rejected.
```

## 🎯 EXPECTED RESULT

With FIX #31:
1. iPhone negotiates `14.1` (only option)
2. Server echoes `14.1` on every response
3. iPhone accepts responses (advances SyncKey)
4. With FIX #30 (Truncated token), emails are displayed!

## 📝 FILES TO MODIFY

1. `app/routers/activesync.py`:
   - Add `protocol_version` parameter to `_eas_headers()`
   - Create separate `_eas_options_headers()`
   - Update OPTIONS handler
   - Update Sync handler to echo client version
   - Update FolderSync handler to echo client version
   - Update Provision handler to echo client version

2. Add logging to track version negotiation:
   ```python
   logger.info(f"Client requested version: {client_version}, echoing back")
   ```

## 🔍 WHY THIS MATTERS

iOS is **strict** about protocol version consistency:
- If you advertise 16.1, iOS expects 16.1 semantics
- If you send 14.1 WBXML with 16.1 negotiated, iOS **silently drops** the response
- The phone never advances SyncKey → infinite loop!

**Solution:** Only advertise what we can actually deliver (14.1 format).

## 🚀 AFTER THIS WORKS

Once stable on 14.1:
1. Gradually add 14.0, 12.1 support
2. Test each version separately
3. Eventually add 16.x support (requires different WBXML structure)
4. Always echo the exact version client requested

