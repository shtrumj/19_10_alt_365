# Testing Guide: HTML Body Fix (CRITICAL FIX #58)

## Current Status: ✅ DEPLOYED

**Date**: October 3, 2025  
**Commit**: `4c8d4f1` - CRITICAL FIX #58: Z-Push-compliant HTML body handling  
**Deployed**: Production (all containers running)

---

## What Was Fixed

The iPhone was showing **"This message has not been downloaded from the server"** when trying to view HTML email bodies. This is now fixed by implementing Z-Push-compliant WBXML structure with:

1. ✅ `AirSyncBase:NativeBodyType` token (0x16) - tells iOS if content is HTML or plain text
2. ✅ `_select_body_content()` helper - standardized body selection logic
3. ✅ Removed global `Content-Type` header - each response sets its own media type
4. ✅ Consistent `InternetCPID=65001` (UTF-8) declaration

---

## How to Test

### Test 1: Send a Rich HTML Email

1. **From another email account**, send an HTML email to `yonatan@shtrum.com` with:
   - **Bold**, *italic*, and <u>underlined</u> text
   - Multiple font colors
   - Bullet points or numbered lists
   - Links (e.g., https://example.com)
   - Multiple paragraphs with spacing
   - HTML tables (if supported)

2. **Example HTML content** to copy/paste:
   ```html
   <h1 style="color: blue;">Test HTML Email</h1>
   <p>This email tests <strong>bold</strong>, <em>italic</em>, and <u>underlined</u> text.</p>
   <p style="color: red;">This paragraph is red.</p>
   <ul>
       <li>First bullet point</li>
       <li>Second bullet point</li>
       <li>Third bullet point</li>
   </ul>
   <p>Here's a link: <a href="https://github.com/shtrumj/365_preorder_with-oprational_activesync">GitHub Repo</a></p>
   <p>If you can see all the formatting, HTML body rendering is working! 🎉</p>
   ```

3. **On your iPhone**:
   - Email should appear **automatically** (push notifications working)
   - Open the email
   - **Expected**: Full HTML rendering with all formatting intact
   - **Not expected**: Plain text or "This message has not been downloaded from the server"

---

### Test 2: Plain Text Email

1. **Send a plain text email** (no HTML) to `yonatan@shtrum.com`

2. **On your iPhone**:
   - Email should appear automatically
   - Open the email
   - **Expected**: Plain text displays correctly
   - Server should send `NativeBodyType=1` (plain text)

---

### Test 3: Monitor Real-Time Activity

**Option A: Use the push monitoring script**
```bash
cd /Users/jonathanshtrum/Downloads/365
./monitor_push.sh
```

This will show:
- ✅ Ping connections (Push mode active)
- 📧 New email notifications
- 🔔 Push triggers

**Option B: Watch ActiveSync logs**
```bash
tail -f /Users/jonathanshtrum/Downloads/365/logs/activesync/activesync.log | jq -r 'select(.event) | "\(.ts) | \(.event) | \(.message // "")"'
```

Look for:
- `sync_emails_sent_wbxml_simple` - server sending emails
- `ping_start` - iPhone maintaining Push connection
- `ping_changes_detected` - new email triggers notification

---

### Test 4: Fetch Existing Messages

1. **On your iPhone**, scroll through your inbox
2. **Tap on older emails** that might not have full bodies downloaded
3. **Expected**: Bodies load immediately with full HTML rendering
4. **Check logs** for `sync_ops_parsed` with `"fetch_ids": ["1:XX"]`

---

## Verification Checklist

Use this checklist to verify all aspects are working:

### ActiveSync Server
- [x] Docker containers running (`docker-compose ps`)
- [x] ActiveSync OPTIONS endpoint responding (`curl -X OPTIONS https://localhost/Microsoft-Server-ActiveSync -k -i`)
- [x] No errors in logs (`docker-compose logs email-system | grep -i error`)

### HTML Body Rendering
- [ ] HTML email displays with full formatting on iPhone
- [ ] No "This message has not been downloaded from the server" error
- [ ] Colors, bold, italic, underline all visible
- [ ] Links are clickable
- [ ] Multiple paragraphs with correct spacing

### Plain Text Fallback
- [ ] Plain text emails display correctly
- [ ] No HTML tags visible in plain text emails

### Push Notifications
- [ ] New emails appear automatically (no need to pull down)
- [ ] Notification appears in iPhone lock screen
- [ ] Badge count updates immediately
- [ ] Monitor script shows `ping_start` and `ping_changes_detected`

### Fetch Command
- [ ] Tapping older emails loads bodies immediately
- [ ] No delay or "downloading" spinner
- [ ] Full HTML rendering on Fetch

---

## Expected WBXML Structure

When you send a test email, the server should generate WBXML like this:

```
<Sync>
  <Collections>
    <Collection>
      <SyncKey>63</SyncKey>
      <CollectionId>1</CollectionId>
      <Class>Email</Class>
      <Status>1</Status>
      <Commands>
        <Add>
          <ServerId>1:49</ServerId>
          <ApplicationData>
            <!-- Email (CP 2) -->
            <Subject>Test HTML Email</Subject>
            <From>sender@example.com</From>
            <To>yonatan@shtrum.com</To>
            <DateReceived>2025-10-03T17:15:00.000Z</DateReceived>
            <MessageClass>IPM.Note</MessageClass>
            <InternetCPID>65001</InternetCPID>  <!-- UTF-8 -->
            <Read>0</Read>
            
            <!-- AirSyncBase (CP 17) -->
            <Body>
              <Type>2</Type>  <!-- 2=HTML, 1=Plain -->
              <EstimatedDataSize>1234</EstimatedDataSize>
              <Truncated>0</Truncated>
              <Data><![CDATA[<html>...</html>]]></Data>
            </Body>
            <NativeBodyType>2</NativeBodyType>  <!-- ⭐ KEY FIX! -->
          </ApplicationData>
        </Add>
      </Commands>
    </Collection>
  </Collections>
</Sync>
```

---

## Troubleshooting

### Issue: Still seeing "This message has not been downloaded"

**Check 1**: Verify the fix is deployed
```bash
cd /Users/jonathanshtrum/Downloads/365
git log --oneline -1
# Should show: 4c8d4f1 CRITICAL FIX #58: Z-Push-compliant HTML body handling
```

**Check 2**: Verify containers are running the new code
```bash
docker-compose ps
# Both containers should show "Up" status
```

**Check 3**: Check for errors in logs
```bash
docker-compose logs email-system | tail -50
```

**Check 4**: Reset iPhone ActiveSync account
- Settings → Mail → Accounts → your account → Delete Account
- Re-add the account
- This forces a fresh FolderSync + Sync with SyncKey=0

---

### Issue: Push notifications not working

**Verify iPhone is in Push mode**:
1. Settings → Mail → Accounts → Fetch New Data
2. **Push** should be ON (toggle is GREEN)
3. Your account should say "Push" (not "Fetch")

**Check Ping connections**:
```bash
./monitor_push.sh
# Should show: "✅ iPhone connected with Ping (Push mode)"
```

---

### Issue: Plain text emails not displaying

**This is expected behavior if**:
- Email genuinely has no HTML version
- Server correctly sends `NativeBodyType=1` (plain text)

**Check logs**:
```bash
tail -f logs/activesync/activesync.log | jq 'select(.event == "sync_emails_sent_wbxml_simple")'
# body_type should be 1 for plain text, 2 for HTML
```

---

## Success Criteria

✅ **Fix is working if**:
1. HTML emails display with full formatting on iPhone
2. No "This message has not been downloaded from the server" errors
3. New emails appear automatically via Push
4. Fetch command loads bodies immediately
5. Logs show `NativeBodyType` being sent for all emails

---

## Next Steps After Testing

### If Everything Works ✅
1. Mark this fix as verified
2. Send more complex emails (images, tables, etc.)
3. Test with multiple devices (iPad, other iPhones)
4. Update documentation with success confirmation

### If Issues Persist ❌
1. Capture full `activesync.log` snippet showing:
   - The Sync request from iPhone
   - The Sync response from server
   - Any error messages
2. Provide WBXML hex dump for analysis
3. Expert can compare against Z-Push reference implementation

---

## Support Commands

```bash
# Check container status
docker-compose ps

# View live logs
docker-compose logs -f email-system

# Monitor push notifications
./monitor_push.sh

# Test ActiveSync endpoint
curl -X OPTIONS https://localhost/Microsoft-Server-ActiveSync -k -i

# View recent Sync activity
tail -50 logs/activesync/activesync.log | jq .

# Restart containers
docker-compose restart

# Rebuild if needed (use cached layers)
docker-compose build email-system && docker-compose up -d
```

---

## Documentation References

- **CRITICAL_FIX_58_HTML_BODY_HANDLING.md** - Technical details of the fix
- **ENABLE_PUSH_NOTIFICATIONS.md** - Push notification setup guide
- **activesync/ACTIVESYNC_COMPLETE_SPECIFICATION.md** - Full ActiveSync protocol reference
- **MS-ASWBXML**: Microsoft specification for WBXML tokens
- **MS-ASCMD**: Microsoft specification for ActiveSync commands

---

## Commit History

```
4c8d4f1 - CRITICAL FIX #58: Z-Push-compliant HTML body handling
c3837ba - Implement event-driven push notifications
424c83f - with contol loop improvement
f14f869 - feat(eas): HTML body + Fetch support
```

**GitHub**: https://github.com/shtrumj/365_preorder_with-oprational_activesync

---

**Good luck with testing! 🎉**

If you see all your HTML formatting on the iPhone, you can celebrate - this was a complex fix requiring deep knowledge of MS-ASWBXML and Z-Push internals!






