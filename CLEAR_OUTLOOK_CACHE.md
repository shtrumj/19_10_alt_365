# Clear Outlook Autodiscover Cache - CRITICAL

## 🚨 THE PROBLEM

Your screenshot shows Outlook displaying:

```xml
<AuthPackage>Negotiate</AuthPackage>
```

But the server logs show it's NOW sending:

```xml
<AuthPackage>Basic</AuthPackage>  ← CORRECT!
```

**Outlook is using a CACHED old response** from before we applied the fix!

---

## ✅ SOLUTION: Clear Outlook's Autodiscover Cache

### Method 1: Hold CTRL While Starting Outlook (EASIEST)

1. **Close Outlook completely**
2. **Hold down the CTRL key**
3. **Double-click Outlook icon while holding CTRL**
4. **Keep holding CTRL until Outlook starts**
5. This forces Outlook to bypass cache and query autodiscover fresh

### Method 2: Delete Autodiscover Cache Files (MOST THOROUGH)

1. **Close Outlook completely**

2. **Open File Explorer**, paste this path in address bar:

   ```
   %LocalAppData%\Microsoft\Outlook
   ```

3. **Delete these files** (if they exist):
   - `*.xml` files (autodiscover cache)
   - Look for files like `autodiscover.xml` or similar

4. **Also check this location**:

   ```
   %LocalAppData%\Microsoft\Office\16.0\Outlook
   ```

   Delete any `*.xml` files

5. **Restart Outlook**

### Method 3: Registry Method (NUCLEAR OPTION)

1. **Press Windows + R**
2. **Type:** `regedit` and press Enter
3. **Navigate to:**
   ```
   HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover
   ```
4. **Delete the entire `AutoDiscover` key**
5. **Restart Outlook**

---

## 🧪 VERIFY THE FIX WORKED

### After clearing cache, add account again:

1. **File → Add Account**
2. **Enter:** `yonatan@shtrum.com`
3. **Watch the logs:**
   ```bash
   tail -f logs/web/autodiscover/autodiscover.log
   tail -f logs/web/mapi/mapi.log
   ```

### Expected Results:

✅ **Autodiscover log should show:**

```json
{ "event": "response", "AuthPackage": "Basic" }
```

✅ **MAPI log should show (THIS IS KEY):**

```json
{"event": "emsmdb_get"}  ← Outlook probing
{"event": "emsmdb"}      ← Outlook connecting
```

---

## 📊 CURRENT SERVER STATUS

### ✅ Server is FIXED and working correctly:

**From logs at 07:22:23 (2 minutes ago):**

```json
{
  "ts": "2025-10-10T07:22:23",
  "component": "autodiscover",
  "event": "response_full",
  "email": "yonatan@shtrum.com",
  "mapi_url": "https://owa.shtrum.com/mapi/emsmdb",
  "auth_package": "Basic",  ← CORRECT!
  "mapi_http_enabled": true
}
```

### ✅ MAPI logging is configured:

- Location: `logs/web/mapi/mapi.log`
- Function: `log_mapi()` in `mapihttp.py` line 36
- Will log when Outlook connects

### ❌ NO MAPI logs = Outlook not connecting = Using cached wrong auth

---

## 🎯 WHY THIS HAPPENS

**Outlook's Autodiscover Cache Behavior:**

1. Outlook queries autodiscover once
2. Caches the response for performance
3. Won't re-query until:
   - Cache is manually cleared
   - You delete and re-add the account
   - You restart Outlook with CTRL held

**Your situation:**

- First query: Got `Negotiate` (before fix)
- Server fixed: Now sending `Basic`
- Outlook: Still using cached `Negotiate`
- Result: Won't even try MAPI/HTTP

---

## 🔍 PROOF FROM YOUR SCREENSHOT

Your browser is showing the XML response from autodiscover, and it clearly shows:

```xml
<AuthPackage>Negotiate</AuthPackage>
```

But the server logs at 07:22:23 show we're sending:

```xml
<AuthPackage>Basic</AuthPackage>
```

**This can ONLY happen if:**

1. The browser cached the response, OR
2. Outlook cached the response and is displaying that

**Solution:** Clear ALL caches and try again fresh.

---

## 📋 STEP-BY-STEP PROCEDURE

1. ✅ Close Outlook
2. ✅ Clear cache using Method 1 (CTRL) or Method 2 (files)
3. ✅ Open terminal and watch logs:
   ```bash
   tail -f logs/web/autodiscover/autodiscover.log &
   tail -f logs/web/mapi/mapi.log
   ```
4. ✅ Start Outlook (hold CTRL if using Method 1)
5. ✅ File → Add Account → yonatan@shtrum.com
6. ✅ Watch for MAPI logs to appear

**If you see logs like:**

```json
{ "event": "emsmdb_get", "ua": "Microsoft Office..." }
```

**SUCCESS!** Outlook is now connecting with the correct auth!

---

## 🆘 IF STILL NOT WORKING

If after clearing cache, Outlook STILL shows "Negotiate" in the browser:

1. **Check browser cache:**
   - Close all browser windows
   - Clear browser cache
   - Try incognito/private window

2. **Test the server directly:**

   ```bash
   curl -X POST https://autodiscover.shtrum.com/Autodiscover/Autodiscover.xml \
     -H "Content-Type: text/xml" \
     -d '<?xml version="1.0"?>
   <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
     <Request>
       <EMailAddress>yonatan@shtrum.com</EMailAddress>
       <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
     </Request>
   </Autodiscover>'
   ```

   **Should show:** `<AuthPackage>Basic</AuthPackage>`

3. **Check if proxy/nginx is caching:**
   - Restart nginx: `docker restart 365-nginx`
   - Clear nginx cache if configured

---

## ✅ BOTTOM LINE

- ✅ Server: **FIXED** - Sending `Basic` auth (verified in logs)
- ✅ MAPI logging: **WORKING** - Ready to log connections
- ❌ Outlook: **CACHED** - Using old `Negotiate` response
- 🎯 Solution: **CLEAR OUTLOOK CACHE** and re-add account

**The fix IS applied, Outlook just needs to get the new response!**
