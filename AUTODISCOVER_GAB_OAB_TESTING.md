# Autodiscover, GAB, and OAB Testing Guide

**Date:** 2025-10-10  
**Status:** ✅ All endpoints implemented and ready for testing

---

## 📋 Overview

This document describes how to test the following Outlook-related endpoints:

1. **Autodiscover (XML)** - Traditional Outlook discovery
2. **Autodiscover (JSON)** - Modern Outlook discovery
3. **OAB (Offline Address Book)** - Offline address list caching
4. **GAB/NSPI** - Global Address List via MAPI/HTTP

---

## 🚀 Quick Start

### Option 1: Automated Testing (Python)

```bash
# Inside Docker
docker exec -it <container> python3 test_scripts/test_autodiscover_gab_oab.py

# Or locally (update BASE_URL in script)
python3 test_scripts/test_autodiscover_gab_oab.py
```

### Option 2: Automated Testing (Bash/curl)

```bash
# Local server
./test_autodiscover_gab_oab.sh localhost:8000 user@example.com

# Production server
./test_autodiscover_gab_oab.sh owa.shtrum.com user@shtrum.com
```

### Option 3: Manual Testing (curl)

See examples below for each endpoint.

---

## 📡 Endpoint Testing

### 1. Autodiscover (XML) - Traditional Outlook

**Purpose:** Allows Outlook to automatically configure server settings

**Endpoint:** `POST /Autodiscover/Autodiscover.xml`

**Test with curl:**

```bash
curl -X POST https://your-server.com/Autodiscover/Autodiscover.xml \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H "User-Agent: Microsoft Office/16.0" \
  -d '<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>user@example.com</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>' \
  -k -v
```

**Expected Response:**

```xml
<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response>
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
      <Protocol>
        <Type>EXHTTP</Type>  <!-- MAPI/HTTP -->
        <Server>your-server.com</Server>
        <SSL>On</SSL>
        <AuthPackage>Basic</AuthPackage>
      </Protocol>
      <Protocol>
        <Type>WEB</Type>  <!-- OWA -->
        <OWAUrl>https://your-server.com/owa/</OWAUrl>
      </Protocol>
      <Protocol>
        <Type>MobileSync</Type>  <!-- ActiveSync -->
        <Server>your-server.com</Server>
      </Protocol>
    </Account>
  </Response>
</Autodiscover>
```

**Key Elements to Check:**
- ✅ `<Type>EXHTTP</Type>` - MAPI/HTTP support for Outlook Desktop
- ✅ `<Type>WEB</Type>` - OWA support
- ✅ `<Type>MobileSync</Type>` - ActiveSync for mobile devices
- ✅ `<Server>` - Your server hostname

---

### 2. Autodiscover (JSON) - Modern Outlook

**Purpose:** Modern Outlook clients use JSON for discovery

**Endpoint:** `GET /autodiscover/autodiscover.json/v1.0/{email}`

**Test with curl:**

```bash
curl -X GET "https://your-server.com/autodiscover/autodiscover.json/v1.0/user@example.com" \
  -H "Accept: application/json" \
  -H "User-Agent: Microsoft Office/16.0" \
  -k -v
```

**Expected Response:**

```json
{
  "User": {
    "DisplayName": "User Name",
    "AutodiscoverVersion": "1.0"
  },
  "Protocol": {
    "Type": "EXHTTP",
    "Server": "your-server.com",
    "SSL": "On",
    "AuthPackage": "Basic",
    "AutodiscoverUrl": "https://your-server.com/autodiscover/autodiscover.xml"
  }
}
```

---

### 3. OAB Manifest - Offline Address Book

**Purpose:** Tells Outlook about available offline address books

**Endpoint:** `GET /oab/oab.xml`

**Test with curl:**

```bash
curl -X GET https://your-server.com/oab/oab.xml \
  -H "User-Agent: Microsoft Office/16.0" \
  -k -v
```

**Expected Response:**

```xml
<?xml version="1.0" encoding="utf-8"?>
<OAB xmlns="http://schemas.microsoft.com/exchange/2003/oab">
  <OAL>
    <Name>Default Global Address List</Name>
    <DN>/o=First Organization/ou=Exchange Administrative Group/cn=addrlists/cn=oabs/cn=default offline address book</DN>
    <Id>default-oab</Id>
    <Version>4.0</Version>
    <Size>102400</Size>
    <LastModified>2025-10-10T12:00:00Z</LastModified>
    <Files>
      <File>
        <Name>browse.oab</Name>
        <Size>51200</Size>
        <SHA1>0000000000000000000000000000000000000000</SHA1>
      </File>
      <File>
        <Name>details.oab</Name>
        <Size>25600</Size>
        <SHA1>1111111111111111111111111111111111111111</SHA1>
      </File>
      <File>
        <Name>rdndex.oab</Name>
        <Size>4096</Size>
        <SHA1>2222222222222222222222222222222222222222</SHA1>
      </File>
    </Files>
  </OAL>
</OAB>
```

**Key Elements:**
- ✅ `<OAL>` - Address list definition
- ✅ `<Files>` - List of OAB data files
- ✅ `browse.oab` - Browse file (required)
- ✅ `details.oab` - Details file (required)
- ✅ `rdndex.oab` - RDN index (required)

---

### 4. OAB Data Files - Address Book Data

**Purpose:** Binary files containing user directory information

**Endpoints:**
- `GET /oab/{oab_id}/browse.oab` - Browse file
- `GET /oab/{oab_id}/details.oab` - Details file
- `GET /oab/{oab_id}/rdndex.oab` - RDN index file

**Test with curl:**

```bash
# Browse file (contains basic user info)
curl -X GET https://your-server.com/oab/default-oab/browse.oab \
  -H "User-Agent: Microsoft Office/16.0" \
  -o browse.oab \
  -k -v

# Details file (contains detailed user properties)
curl -X GET https://your-server.com/oab/default-oab/details.oab \
  -H "User-Agent: Microsoft Office/16.0" \
  -o details.oab \
  -k -v

# RDN index file (contains distinguished name index)
curl -X GET https://your-server.com/oab/default-oab/rdndex.oab \
  -H "User-Agent: Microsoft Office/16.0" \
  -o rdndex.oab \
  -k -v
```

**Expected Response:**
- Binary data files
- Content-Type: `application/octet-stream`
- File sizes vary based on user count

**File Format (Simplified):**

```
browse.oab:
- Header: "OAB4" (4 bytes)
- User count (4 bytes, little-endian)
- For each user:
  - Display name length (2 bytes)
  - Display name (UTF-8)
  - Email length (2 bytes)
  - Email (UTF-8)
```

---

### 5. NSPI/GAB - Global Address List (MAPI/HTTP)

**Purpose:** Provides Global Address List via MAPI/HTTP protocol

**Endpoint:** `POST /mapi/nspi`

**Test with curl:**

```bash
# Create NSPI GetMatches request (binary)
printf '\x01\x00\x00\x00\x00\x00\x00\x00\x64\x00\x00\x00' > nspi_request.bin

# Send request
curl -X POST https://your-server.com/mapi/nspi \
  -H "Content-Type: application/mapi-http" \
  -H "User-Agent: Microsoft Office/16.0" \
  -H "X-RequestType: GetMatches" \
  --data-binary "@nspi_request.bin" \
  -o nspi_response.bin \
  -k -v
```

**Request Format:**
```
Byte 0-3: Operation code (0x01 = GetMatches)
Byte 4-7: Flags
Byte 8-11: Max entries (100 = 0x64)
```

**Response Format:**
```
Byte 0-3: Status code (0 = success)
Byte 4-7: User count
For each user:
  - Name length (2 bytes)
  - Name (UTF-8)
  - Email length (2 bytes)
  - Email (UTF-8)
```

---

## 🔍 Verification Checklist

### Autodiscover (XML)
- [ ] HTTP 200 response
- [ ] Valid XML structure
- [ ] Contains EXHTTP protocol (MAPI/HTTP)
- [ ] Contains WEB protocol (OWA)
- [ ] Contains MobileSync protocol (ActiveSync)
- [ ] Server hostname is correct
- [ ] SSL is set to "On"

### Autodiscover (JSON)
- [ ] HTTP 200 response
- [ ] Valid JSON structure
- [ ] Contains Protocol object
- [ ] Contains AutodiscoverUrl
- [ ] Type is "EXHTTP"

### OAB Manifest
- [ ] HTTP 200 response
- [ ] Valid XML structure
- [ ] Contains OAL element
- [ ] Lists browse.oab file
- [ ] Lists details.oab file
- [ ] Lists rdndex.oab file
- [ ] Version is 4.0

### OAB Data Files
- [ ] browse.oab returns binary data (HTTP 200)
- [ ] details.oab returns binary data (HTTP 200)
- [ ] rdndex.oab returns binary data (HTTP 200)
- [ ] Content-Type is application/octet-stream
- [ ] Files are non-zero size

### NSPI/GAB
- [ ] HTTP 200 response
- [ ] Response is binary data
- [ ] First 4 bytes are status code (0x00 = success)
- [ ] Next 4 bytes are user count
- [ ] Response contains user data

---

## 🐛 Troubleshooting

### Issue: Autodiscover returns 404

**Cause:** Endpoint not registered or URL case mismatch

**Fix:**
```bash
# Check available routes
docker exec -it <container> python3 -c "
from app.main import app
for route in app.routes:
    if 'autodiscover' in route.path.lower():
        print(route.path, route.methods)
"
```

### Issue: OAB files return 404

**Cause:** OAB ID mismatch or route not registered

**Fix:**
- Verify OAB ID is "default-oab"
- Check logs: `docker logs <container> | grep oab`

### Issue: NSPI returns empty response

**Cause:** No users in database or NSPI not parsing request

**Fix:**
```bash
# Check user count
docker exec -it <container> python3 -c "
from app.database import SessionLocal, User
db = SessionLocal()
print(f'Users: {db.query(User).count()}')
db.close()
"
```

### Issue: Autodiscover works but Outlook doesn't connect

**Cause:** Server URLs in Autodiscover response don't match actual server

**Fix:**
- Verify HOSTNAME in config matches DNS
- Check SSL certificates are valid
- Ensure all protocols (EXHTTP, WEB, etc.) have correct URLs

---

## 📊 Test Results

### Expected Output (All Tests Passing)

```
✅ PASS - Autodiscover XML Response (HTTP 200)
✅ PASS - Has EXHTTP protocol (MAPI/HTTP support)
✅ PASS - Has WEB protocol (OWA support)
✅ PASS - Has MobileSync protocol (ActiveSync support)

✅ PASS - Autodiscover JSON Response (HTTP 200)
✅ PASS - Has Protocol field
✅ PASS - Has AutodiscoverUrl

✅ PASS - OAB Manifest (HTTP 200)
✅ PASS - Has OAB structure
✅ PASS - Has browse.oab file
✅ PASS - Has details.oab file
✅ PASS - Has rdndex.oab file

✅ PASS - browse.oab (Size: 51200 bytes)
✅ PASS - details.oab (Size: 25600 bytes)
✅ PASS - rdndex.oab (Size: 4096 bytes)

✅ PASS - NSPI/GAB Response (Size: 8192 bytes)
✅ PASS - Has response data
```

---

## 🔗 Related Documentation

- **Autodiscover:** [MS-OXDSCLI] - Autodiscover Publishing and Lookup Protocol
- **OAB:** [MS-OXWOAB] - Offline Address Book File Format
- **NSPI:** [MS-OXNSPI] - Name Service Provider Interface (NSPI) Protocol
- **MAPI/HTTP:** [MS-OXCMAPIHTTP] - MAPI/HTTP Transport Protocol

---

## 📝 Implementation Files

| Endpoint | File | Status |
|----------|------|--------|
| Autodiscover XML | `app/routers/autodiscover.py` | ✅ Complete |
| Autodiscover JSON | `app/routers/autodiscover.py` | ✅ Complete |
| OAB Manifest | `app/routers/oab.py` | ✅ Complete |
| OAB Data Files | `app/routers/oab.py` | ✅ Complete |
| NSPI/GAB | `app/routers/mapihttp.py` | ✅ Complete |

---

## ✅ Summary

All Autodiscover, GAB, and OAB endpoints are **fully implemented** and ready for testing:

1. **Autodiscover (XML & JSON)** - Allows Outlook auto-configuration
2. **OAB Manifest & Files** - Enables offline address book downloads
3. **NSPI/GAB** - Provides Global Address List via MAPI/HTTP

Use the test scripts provided to verify all endpoints are functioning correctly.

---

_Last Updated: 2025-10-10_

