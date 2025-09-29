# Outlook Professional Plus 2021 Setup Guide
## For 365 Email System Exchange Server

### 🎯 **Issue Identified**
Outlook Professional Plus 2021 has specific requirements and tries to connect to Office 365 endpoints first, which prevents it from using custom Exchange servers.

---

## 📋 **Step-by-Step Solution**

### **Step 1: Apply Registry Fix (CRITICAL)**
1. **Download** the `outlook_2021_registry_fix.reg` file to your Windows machine
2. **Right-click** on the file and select "Merge" or double-click to import
3. **Click "Yes"** to confirm registry modification
4. **Restart Outlook** completely (close and reopen)

**What this does:**
- Prevents Outlook from trying Office 365 endpoints first
- Enables detailed Autodiscover logging for troubleshooting
- Forces Outlook to use your custom Exchange server

---

### **Step 2: Create New Outlook Profile**
1. **Close Outlook** completely
2. **Open Control Panel** → Mail (32-bit) → Show Profiles
3. **Click "Add"** to create a new profile
4. **Name it** "Exchange Custom" or similar
5. **Set as default** profile
6. **Configure** with these settings:
   - **Email:** `yonatan@shtrum.com`
   - **Password:** `Gib$0n579!`
   - **Server:** Let Outlook auto-detect (it will use Autodiscover)

---

### **Step 3: Alternative - Local Autodiscover XML (If Step 1-2 Fails)**
1. **Create folder:** `C:\temp\`
2. **Copy** `outlook_2021_local_autodiscover.xml` to `C:\temp\autodiscover.xml`
3. **Apply additional registry setting:**
   ```registry
   [HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover]
   "PreferLocalXML"=dword:00000001
   "LocalXMLPath"="C:\\temp\\autodiscover.xml"
   ```

---

### **Step 4: Enable Autodiscover Logging**
The registry fix automatically enables logging. Check these files for troubleshooting:
- **Client logs:** `C:\temp\autodiscover.log`
- **Server logs:** Available in the admin panel

---

### **Step 5: Test Connection**
1. **Open Outlook** with the new profile
2. **Wait 2-3 minutes** for Autodiscover to complete
3. **Check for errors** in `C:\temp\autodiscover.log`
4. **Verify connection** by sending/receiving test emails

---

## 🔧 **Troubleshooting**

### **If Outlook Still Gets Stuck:**
1. **Check registry settings** were applied correctly
2. **Verify DNS resolution:** `nslookup autodiscover.shtrum.com`
3. **Test Autodiscover manually:**
   ```bash
   curl -k -X POST "https://autodiscover.shtrum.com/autodiscover/autodiscover.xml" \
   -H "Content-Type: text/xml" \
   -H "Authorization: Basic eW9uYXRhbkBzaHRydW0uY29tOkdpYiQwbjU3OSE=" \
   -d @test_request.xml
   ```
4. **Check client logs** in `C:\temp\autodiscover.log`
5. **Try creating another new profile** with a different name

### **Common Outlook 2021 Issues:**
- **Cached credentials:** Clear saved passwords in Credential Manager
- **Proxy settings:** Disable proxy for Outlook if using corporate network
- **Antivirus interference:** Temporarily disable email scanning
- **Windows updates:** Ensure Outlook is updated to latest version

---

## 📊 **Expected Behavior After Fix**

1. **Autodiscover phase:** 30-60 seconds
2. **MAPI connection:** Should connect to `https://owa.shtrum.com/mapi/emsmdb`
3. **Folder sync:** Inbox, Sent Items, etc. should appear
4. **Address book:** Global Address List should be available
5. **Calendar:** Calendar items should sync

---

## 🚨 **If All Else Fails**

Contact your IT administrator to:
1. **Verify firewall settings** allow HTTPS traffic to owa.shtrum.com
2. **Check corporate policies** that might block custom Exchange servers
3. **Consider domain trust** requirements for Exchange connectivity
4. **Test from a non-domain machine** to isolate domain policy issues

---

## 📞 **Support Information**

- **Server Status:** Check admin panel at `https://owa.shtrum.com/owa/admin`
- **SMTP Logs:** Available in admin panel for troubleshooting
- **Autodiscover Endpoint:** `https://autodiscover.shtrum.com/autodiscover/autodiscover.xml`
- **MAPI Endpoint:** `https://owa.shtrum.com/mapi/emsmdb`
