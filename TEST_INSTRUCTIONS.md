# 📱 TEST INSTRUCTIONS - ALL FIXES APPLIED!

## ✅ FIXES APPLIED (Built at 18:24, Oct 2)

### FIX #30: Truncated Token
- Changed from `0x0C` (empty) to `0x4C 03 '0' 00 01` (with content)
- Per MS-ASWBXML: Truncated is a boolean container, not empty tag

### FIX #31: Protocol Version Negotiation
- Separated `_eas_options_headers()` and `_eas_headers(protocol_version)`
- Cap advertised versions to 14.1 only (removed 16.x)
- Echo client's `MS-ASProtocolVersion` header on all POST responses

### FIX #31B: Logger Import
- Added missing `import logging` and `logger = logging.getLogger(__name__)`
- Fixed 500 Internal Server Error on all POST requests

### FIX #32: ApplicationData Token (THE SMOKING GUN!)
- Changed from `0x4F` (Collection) to `0x5D` (ApplicationData)
- Per MS-ASWBXML AirSync cp0: ApplicationData = 0x1D + 0x40 = 0x5D
- iOS was rejecting ALL email items due to this!

### FIX #33: MoreAvailable Token (PAGINATION FIX!)
- Changed from `0x16` (Commands) to `0x1B` (MoreAvailable)
- Per MS-ASWBXML AirSync cp0: MoreAvailable = 0x1B (empty element)
- iOS was looping "idempotently" with same SyncKey due to this!

---

## 🧪 HOW TO TEST

### Step 1: Delete iPhone Exchange Account
1. Open iPhone **Settings**
2. Go to **Mail** → **Accounts**
3. Tap on your Exchange account (`yonatan@shtrum.com`)
4. Tap **Delete Account**
5. Confirm deletion

### Step 2: Re-Add iPhone Exchange Account
1. Open iPhone **Settings**
2. Go to **Mail** → **Accounts** → **Add Account**
3. Select **Exchange**
4. Enter:
   - **Email**: `yonatan@shtrum.com`
   - **Password**: `[your password]`
5. Tap **Next**
6. Server should auto-fill: `owa.shtrum.com`
7. Tap **Sign In**
8. Wait for account to sync...

### Step 3: Monitor Logs
Open terminal and watch logs in real-time:

```bash
tail -f logs/activesync/activesync.log | jq -r '"\(.ts | sub("T"; " ") | sub("Z"; "")) | \(.event) | \(.sync_key // "N/A") | \(.client_sync_key // "N/A") | \(.key_progression // "")"'
```

---

## ✅ EXPECTED LOG PATTERN (CORRECT BEHAVIOR)

```
18:30:00 | options                       | N/A | N/A | 
18:30:01 | request_received (provision)  | N/A | N/A |
18:30:01 | request_received (foldersync) | N/A | 0   |
18:30:01 | foldersync_initial_sync       | 1   | 0   |
18:30:02 | request_received (sync)       | N/A | 0   | ← Initial sync
18:30:02 | sync_initial_wbxml            | 1   | 0   | ← Empty response
18:30:03 | request_received (sync)       | N/A | 1   | ← Client confirms!
18:30:03 | sync_client_confirmed_simple  | 2   | 1   | 1→2
18:30:03 | sync_emails_sent_wbxml_simple | 2   | 1   | 1→2
18:30:04 | request_received (sync)       | N/A | 2   | ← Client confirms again!
18:30:04 | sync_client_confirmed_simple  | 3   | 2   | 2→3
18:30:04 | sync_emails_sent_wbxml_simple | 3   | 2   | 2→3
18:30:05 | request_received (sync)       | N/A | 3   | ← Progressive!
18:30:05 | sync_client_confirmed_simple  | 4   | 3   | 3→4
...until all 19 emails downloaded!
```

**Key indicators of success:**
- ✅ `client_sync_key` advances: 0 → 1 → 2 → 3 → 4 → ...
- ✅ `key_progression` shows: "1→2", "2→3", "3→4", ...
- ✅ NO "sync_resend_pending" events!
- ✅ NO resets to `client_sync_key: "0"`!

---

## ❌ FAILURE PATTERN (OLD BEHAVIOR - SHOULD NOT HAPPEN NOW!)

```
18:30:00 | options                       | N/A | N/A | 
18:30:01 | request_received (sync)       | N/A | 0   |
18:30:01 | sync_initial_wbxml            | 1   | 0   |
18:30:02 | request_received (sync)       | N/A | 1   |
18:30:02 | sync_client_confirmed_simple  | 2   | 1   | 1→2
18:30:03 | request_received (sync)       | N/A | 1   | ← STUCK! Not advancing!
18:30:03 | sync_resend_pending           | 2   | 1   | ← Resending same batch!
18:30:04 | request_received (sync)       | N/A | 0   | ← RESET! Bad sign!
...infinite loop...
```

**Indicators of failure:**
- ❌ `client_sync_key` stuck at same value (e.g., always 1)
- ❌ `sync_resend_pending` events appear
- ❌ iPhone resets to `client_sync_key: "0"`

---

## 📧 EXPECTED RESULT IN MAIL APP

1. **After ~30 seconds**: First batch of emails appears (4 emails)
2. **After ~60 seconds**: More emails appear (progressive download)
3. **After ~2-3 minutes**: All 19 emails are visible in inbox
4. **No errors**, no infinite syncing indicator

---

## 🔍 VERIFICATION CHECKLIST

After testing, verify:

- [ ] iPhone account syncs without errors
- [ ] Logs show progressive SyncKey advancement (0→1→2→3→...)
- [ ] NO "sync_resend_pending" events in logs
- [ ] NO resets to SyncKey=0 in logs
- [ ] Emails appear in iPhone Mail app
- [ ] All 19 test emails are visible

---

## 🐛 IF IT STILL DOESN'T WORK

1. **Capture the WBXML hex**:
   - Look for `wbxml_full_hex` in the latest `sync_emails_sent_wbxml_simple` event
   - Copy the entire hex string

2. **Check the tail bytes**:
   - Last 20 bytes should end with: `... 01 01 1B 01 01 01` (with MoreAvailable)
   - Or: `... 01 01 01 01 01` (without MoreAvailable)
   - Should NOT end with: `... 01 01 16 01 01 01` (wrong token!)

3. **Provide feedback**:
   - Latest 50 lines of `logs/activesync/activesync.log`
   - Specific behavior observed on iPhone
   - Any error messages

---

## 📚 REFERENCE DOCUMENTS

- `CRITICAL_FIX_32_APPLICATIONDATA.md` - ApplicationData token fix
- `CRITICAL_FIX_33_MOREAVAILABLE.md` - MoreAvailable token fix
- `EXPERT_DIAGNOSIS_FIX31.md` - Protocol version negotiation
- `AIRSYNCBASE_TOKENS_VERIFIED.md` - Token reference table

---

🚀 **ALL FIXES ARE APPLIED - READY TO TEST!**

Last rebuilt: 18:24:37, Oct 2, 2025
Server state: Cleared for fresh test
Docker: Running with latest code
