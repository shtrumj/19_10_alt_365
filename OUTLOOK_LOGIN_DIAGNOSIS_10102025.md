# Outlook Desktop Login Failure - Diagnosis and Fix

**Date:** 2025-10-10  
**Issue:** Outlook cannot log on - "missing required information" error  
**Status:** ✅ ROOT CAUSE IDENTIFIED - FIX APPLIED

---

## 🔍 DIAGNOSIS SUMMARY

### What Was Found

#### ✅ Autodiscover is Working

- Outlook is successfully reaching autodiscover endpoint
- Latest request: `2025-10-10T07:07:22Z`
- User Agent: `Microsoft Office/16.0 (Windows NT 10.0; MAPICPL 16.0.14334; Pro)`
- Email: `yonatan@shtrum.com`
- Response: HTTP 200, complete XML with all protocols

#### ❌ CRITICAL ISSUE: No MAPI/HTTP Requests

- **ZERO MAPI/HTTP connection attempts after autodiscover**
- No `/mapi/emsmdb` requests in logs since Oct 7 (only a curl test)
- Outlook gets settings but **refuses to connect**

### 🎯 ROOT CAUSE

**Authentication Mismatch:**

1. Autodiscover response was sending: `<AuthPackage>Negotiate</AuthPackage>`
2. "Negotiate" means Kerberos/NTLM authentication
3. Your MAPI/HTTP endpoint expects Basic Authentication
4. Outlook receives "Negotiate", attempts Kerberos, fails, and gives up silently
5. **Result: "Missing required information" error**

---

## 🔧 FIX APPLIED

### Change 1: Autodiscover Auth Package

**File:** `app/routers/autodiscover.py`

**Changed:**

```xml
<AuthPackage>Negotiate</AuthPackage>
```

**To:**

```xml
<AuthPackage>Basic</AuthPackage>
```

**Why:** This tells Outlook to use Basic Authentication (username/password) instead of Kerberos/NTLM, which matches what our MAPI/HTTP endpoint supports.

### Change 2: Enhanced Logging

**Added full autodiscover response logging:**

- Logs complete XML response
- Logs MAPI URL, auth type, protocols offered
- Helps diagnose future issues

---

## 📊 BEFORE vs AFTER

### Before (Broken)

```
1. Outlook → Autodiscover: "Get settings for yonatan@shtrum.com"
2. Server → Outlook: "Use MAPI/HTTP with Negotiate auth"
3. Outlook → (tries Kerberos, fails)
4. Outlook → User: "Cannot log on, missing information"
5. NO MAPI requests made
```

### After (Fixed)

```
1. Outlook → Autodiscover: "Get settings for yonatan@shtrum.com"
2. Server → Outlook: "Use MAPI/HTTP with Basic auth"
3. Outlook → MAPI/HTTP: POST /mapi/emsmdb with Basic Auth
4. Server → Outlook: (MAPI Connect response)
5. Outlook connects successfully ✅
```

---

## 🧪 TESTING THE FIX

### Step 1: Restart the Application

```bash
# If running in Docker
docker restart <container_name>

# If running locally
# Kill the process and restart
```

### Step 2: Delete Old Outlook Profile

**Critical:** Outlook caches autodiscover responses. You MUST delete the old profile:

1. Open Outlook
2. File → Account Settings → Account Settings
3. Select the yonatan@shtrum.com account
4. Click "Remove"
5. Click "Yes" to confirm

### Step 3: Create New Profile

1. File → Add Account
2. Enter: `yonatan@shtrum.com`
3. **Do NOT use manual setup** - Let autodiscover work
4. Outlook will say "Searching for your mail server settings..."
5. Enter password when prompted
6. Click "Connect"

### Step 4: Monitor Logs

**Terminal 1 - Watch Autodiscover:**

```bash
tail -f logs/web/autodiscover/autodiscover.log | grep "yonatan@shtrum.com"
```

**Terminal 2 - Watch MAPI/HTTP:**

```bash
tail -f logs/web/mapi/mapi.log
```

**Expected:**

1. You'll see autodiscover request
2. **NEW:** You should now see `/mapi/emsmdb` GET request (Outlook probing)
3. **NEW:** You should see `/mapi/emsmdb` POST request (MAPI Connect)
4. Outlook should show "Connected" or start syncing

---

## 🔍 HOW TO VERIFY IT'S FIXED

### Success Indicators

✅ **Autodiscover logs show Basic auth:**

```json
{
  "auth_package": "Basic",
  "mapi_http_enabled": true
}
```

✅ **MAPI logs show connection attempts:**

```json
{
  "event": "emsmdb_get",
  "ua": "Microsoft Office/16.0",
  "method": "GET"
}
```

✅ **Outlook shows:**

- "Connected" status
- or "Updating inbox..."
- or folder list appears

### Failure Indicators (if still broken)

❌ **No MAPI requests after autodiscover**

- Check if Docker restarted properly
- Check if code changes were applied

❌ **Still shows "Cannot log on"**

- Clear Outlook's autodiscover cache (delete profile)
- Check password is correct
- Verify MAPI endpoint is accessible

---

## 📁 LOG FILES TO CHECK

### 1. Autodiscover Logs

**Location:** `logs/web/autodiscover/autodiscover.log`

**What to look for:**

```bash
grep "yonatan@shtrum.com" logs/web/autodiscover/autodiscover.log | tail -5
```

**Expected:** Recent requests with `auth_package: Basic`

### 2. MAPI/HTTP Logs

**Location:** `logs/web/mapi/mapi.log`

**What to look for:**

```bash
grep "Microsoft Office" logs/web/mapi/mapi.log | tail -10
```

**Expected:** Connection attempts from Outlook

### 3. Outlook Debug Logs

**Location:** `logs/outlook_debug/communication.log`

**What to look for:**

```bash
tail -20 logs/outlook_debug/communication.log
```

**Expected:** MAPI requests logged

---

## 🐛 TROUBLESHOOTING

### Issue: Still no MAPI requests

**Solution 1: Clear Outlook Cache**

```
1. Close Outlook
2. Windows + R → %localappdata%\Microsoft\Outlook
3. Delete all .ost and .nst files
4. Restart Outlook
```

**Solution 2: Test MAPI Endpoint Manually**

```bash
# Test if MAPI endpoint is accessible
curl -X GET https://owa.shtrum.com/mapi/emsmdb -v

# Expected: HTTP 401 with WWW-Authenticate header
```

**Solution 3: Check Autodiscover DNS**

```bash
# Verify autodiscover subdomain
nslookup autodiscover.shtrum.com

# Expected: Should resolve to your server IP
```

### Issue: Authentication fails

**Check user credentials:**

```bash
docker exec -it <container> python3 -c "
from app.database import SessionLocal, User
from app.auth import verify_password

db = SessionLocal()
user = db.query(User).filter(User.email == 'yonatan@shtrum.com').first()
if user:
    print(f'User exists: {user.email}')
    print(f'Password check: {verify_password(\"your-password\", user.hashed_password)}')
else:
    print('User not found!')
db.close()
"
```

### Issue: SSL/TLS errors

**Check certificate:**

```bash
# Verify SSL certificate is valid
openssl s_client -connect owa.shtrum.com:443 -servername owa.shtrum.com

# Expected: Should show valid certificate
```

---

## 📚 TECHNICAL DETAILS

### Why "Negotiate" Failed

**Negotiate Authentication Flow:**

1. Client requests resource
2. Server responds: `401 WWW-Authenticate: Negotiate`
3. Client attempts Kerberos ticket
4. **FAILS:** No Kerberos infrastructure (Active Directory)
5. Client falls back to NTLM
6. **FAILS:** NTLM not properly implemented
7. Client gives up

**Basic Authentication Flow:**

1. Client requests resource with `Authorization: Basic base64(user:pass)`
2. Server verifies credentials
3. Server responds with data
4. **SUCCESS:** Simple, reliable, works everywhere

### Why This Wasn't Caught Earlier

1. iPhone/ActiveSync uses different auth flow (works fine)
2. OWA uses cookie-based auth (works fine)
3. Only MAPI/HTTP Outlook Desktop affected
4. Autodiscover returned settings but Outlook never connected
5. No MAPI logs = no obvious errors to debug

---

## ✅ RESOLUTION CHECKLIST

- [x] Identified root cause (Auth package mismatch)
- [x] Changed AuthPackage from "Negotiate" to "Basic"
- [x] Added enhanced logging for future debugging
- [ ] **Restart application** (you need to do this)
- [ ] **Delete old Outlook profile** (you need to do this)
- [ ] **Create new Outlook profile** (you need to do this)
- [ ] **Verify MAPI requests appear in logs** (you need to check this)

---

## 🎯 NEXT STEPS

1. **Restart the Docker container:**

   ```bash
   docker restart <container>
   ```

2. **Delete the Outlook profile for yonatan@shtrum.com**

3. **Add account again in Outlook**

4. **Watch the logs:**

   ```bash
   tail -f logs/web/mapi/mapi.log
   ```

5. **Report back:**
   - Do you see MAPI requests now?
   - Does Outlook show "Connected"?
   - Any errors in logs?

---

## 📞 IF STILL NOT WORKING

If after applying the fix and restarting, Outlook still won't connect:

1. **Capture full autodiscover response:**

   ```bash
   curl -X POST https://autodiscover.shtrum.com/Autodiscover/Autodiscover.xml \
     -H "Content-Type: text/xml" \
     -d '<?xml version="1.0"?>
   <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
     <Request>
       <EMailAddress>yonatan@shtrum.com</EMailAddress>
       <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
     </Request>
   </Autodiscover>' | xmllint --format -
   ```

2. **Test MAPI endpoint:**

   ```bash
   curl -X GET https://owa.shtrum.com/mapi/emsmdb -v -u yonatan@shtrum.com:password
   ```

3. **Check both logs and share:**
   - `logs/web/autodiscover/autodiscover.log` (last 10 lines)
   - `logs/web/mapi/mapi.log` (all lines)
   - Outlook error message (exact text)

---

**Status:** Fix applied, awaiting testing ⏳
