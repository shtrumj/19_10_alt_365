# Autodiscover Namespace Mismatch Fix

**Date**: 2025-10-10  
**Status**: ✅ **FIXED**

---

## Problem

The Microsoft Connectivity Analyzer showed autodiscover responses as "empty" with the error:
> "The Response element in the payload was null."

However, server logs proved the response was **4042 bytes** (full response), not empty!

---

## Root Cause

**XML Namespace Mismatch**

The Microsoft Connectivity Analyzer (and ActiveSync clients) use strict XML namespace parsing:

1. **Microsoft RCA requested**: `mobilesync/responseschema/2006` (ActiveSync format)
2. **Server responded with**: `outlook/responseschema/2006a` (Outlook/EXCH format)
3. **Result**: Parser looked for `<Response xmlns="mobilesync...">`, found `<Response xmlns="outlook...">`, treated as "not found" → reported as "null"

---

## Solution

Modified `app/routers/autodiscover.py` to detect the requested schema and return the matching format:

### Code Changes

```python
# Detect AcceptableResponseSchema in request
schema_match = re.search(
    r"<AcceptableResponseSchema>([^<]+)</AcceptableResponseSchema>", text, re.I
)
if schema_match:
    schema_value = schema_match.group(1).strip()
    if "mobilesync" in schema_value.lower():
        # ActiveSync/MobileSync request
        response_schema = "http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006"
        is_mobilesync_request = True
    elif schema_value.endswith("/2006a"):
        response_schema = "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"

# Generate appropriate format
if is_mobilesync_request:
    # Return simplified ActiveSync/MobileSync format
    xml = """<?xml version="1.0"?>
<Autodiscover xmlns="...">
  <Response xmlns="mobilesync/responseschema/2006">
    <Action>
      <Settings>
        <Server>
          <Type>MobileSync</Type>
          <Url>https://owa.shtrum.com/Microsoft-Server-ActiveSync</Url>
        </Server>
      </Settings>
    </Action>
  </Response>
</Autodiscover>"""
else:
    # Return full Outlook/EXCH format (existing)
    xml = """...<Response xmlns="outlook/responseschema/2006a">..."""
```

---

## Response Formats

### ActiveSync/MobileSync Format (NEW)

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006">
    <Culture>en:us</Culture>
    <User>
      <DisplayName>Yehonathan Shtrum</DisplayName>
      <EMailAddress>yonatan@shtrum.com</EMailAddress>
    </User>
    <Action>
      <Settings>
        <Server>
          <Type>MobileSync</Type>
          <Url>https://owa.shtrum.com/Microsoft-Server-ActiveSync</Url>
          <Name>https://owa.shtrum.com/Microsoft-Server-ActiveSync</Name>
        </Server>
      </Settings>
    </Action>
  </Response>
</Autodiscover>
```

### Outlook/EXCH Format (EXISTING)

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a">
    <Account>
      <Protocol><Type>EXCH</Type>...
      <Protocol><Type>WEB</Type>...
      <Protocol><Type>MobileSync</Type>...
      <Protocol><Type>SMTP</Type>...
    </Account>
  </Response>
</Autodiscover>
```

---

## Verification

### MobileSync Request Test
```bash
curl -X POST https://owa.shtrum.com/Autodiscover/Autodiscover.xml \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0"?><Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/mobilesync/requestschema/2006"><Request><EMailAddress>yonatan@shtrum.com</EMailAddress><AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006</AcceptableResponseSchema></Request></Autodiscover>' \
  -k
```

**Result**: ✅ Returns MobileSync format with correct namespace

### Outlook Request Test
```bash
curl -X POST https://owa.shtrum.com/Autodiscover/Autodiscover.xml \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0"?><Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006"><Request><EMailAddress>yonatan@shtrum.com</EMailAddress><AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema></Request></Autodiscover>' \
  -k
```

**Result**: ✅ Returns Outlook format with correct namespace

---

## Impact

- **Microsoft Connectivity Analyzer**: Should now pass ActiveSync autodiscover test
- **iOS/Android devices**: Will receive correct ActiveSync autodiscover format
- **Outlook Desktop**: Still receives full Outlook/EXCH autodiscover format with MAPI/HTTP settings
- **Backwards compatible**: All existing clients continue to work

---

## Deployment

1. Modified `app/routers/autodiscover.py`
2. Rebuilt Docker image with `docker-compose down && docker-compose up -d --build --force-recreate`
3. Tested both formats - both working correctly

---

## Status

✅ **FIXED** - Autodiscover now returns the correct XML namespace based on the client's request.
