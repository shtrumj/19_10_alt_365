# Microsoft ActiveSync - Complete Implementation Specification

**Version**: ActiveSync 14.1  
**Status**: Production-Ready (Oct 3, 2025)  
**Tested**: iPhone/iOS Mail Client

---

## 📚 Table of Contents

1. [WBXML Fundamentals](#wbxml-fundamentals)
2. [Code Pages & Token Mappings](#code-pages--token-mappings)
3. [Protocol Flow](#protocol-flow)
4. [State Machine Implementation](#state-machine-implementation)
5. [WBXML Builder Implementation](#wbxml-builder-implementation)
6. [Common Pitfalls & Solutions](#common-pitfalls--solutions)
7. [Testing & Verification](#testing--verification)
8. [Microsoft Specifications Reference](#microsoft-specifications-reference)

---

## 🔤 WBXML Fundamentals

### What is WBXML?

WBXML (WAP Binary XML) is a binary representation of XML designed to reduce data size and parsing overhead. ActiveSync uses WBXML for ALL command/response bodies.

### WBXML Structure

```
[Header] [Body]

Header (4-6 bytes):
  - Version: 0x03 (WBXML 1.3)
  - Public Identifier: 0x01 (unknown/no DTD)
  - Charset: 0x6A (UTF-8, 106 decimal)
  - String Table Length: 0x00 (no string table)
  
Example: 03 01 6A 00
```

### Control Tokens

| Token | Hex  | Description |
|-------|------|-------------|
| END | 0x01 | Close current element |
| STR_I | 0x03 | Inline string follows (null-terminated UTF-8) |
| SWITCH_PAGE | 0x00 | Change code page (followed by page number) |

### Content Flag

**CRITICAL**: All element tokens have a "content" variant:
- **Base Token**: No content (empty element like `<Tag/>`)
- **Content Token**: Base + 0x40 (has children or text)

Example:
```
0x0F = <Collection/> (empty)
0x4F = <Collection>...</Collection> (with content)
```

---

## 📖 Code Pages & Token Mappings

### Code Page 0: AirSync

**Purpose**: Core sync structure elements

| Element | Base | +Content | Hex (Content) | Usage |
|---------|------|----------|---------------|-------|
| Sync | 0x05 | 0x45 | `45` | Root element for Sync command |
| Responses | 0x06 | 0x46 | `46` | Server-side change responses (not used in our impl) |
| Add | 0x07 | 0x47 | `47` | Add new item to collection |
| Change | 0x08 | 0x48 | `48` | Update existing item |
| Delete | 0x09 | 0x49 | `49` | Remove item |
| Fetch | 0x0A | 0x4A | `4A` | Retrieve full item details |
| SyncKey | 0x0B | 0x4B | `4B` | Synchronization state identifier |
| ClientId | 0x0C | 0x4C | `4C` | Client-generated temp ID |
| ServerId | 0x0D | 0x4D | `4D` | **REQUIRED** Server-assigned unique ID |
| Status | 0x0E | 0x4E | `4E` | Result code (1=success, 3=conflict, etc) |
| Collection | 0x0F | 0x4F | `4F` | Container for folder sync |
| Class | 0x10 | 0x50 | `50` | Collection type (Email, Calendar, Contacts) |
| CollectionId | 0x12 | 0x52 | `52` | Folder identifier |
| GetChanges | 0x13 | 0x53 | `53` | Flag: request changes (0 or 1) |
| MoreAvailable | 0x14 | 0x54 | `14` | **NO CONTENT** - More items beyond WindowSize |
| WindowSize | 0x15 | 0x55 | `55` | Max items per sync (client-requested) |
| Commands | 0x16 | 0x56 | `56` | Container for Add/Change/Delete |
| Options | 0x17 | 0x57 | `57` | Sync options container |
| FilterType | 0x18 | 0x58 | `58` | Time filter (0=all, 3=1week, 5=1month) |
| Collections | 0x1C | 0x5C | `5C` | Container for multiple Collection elements |
| ApplicationData | 0x1D | 0x5D | `5D` | **CRITICAL** Wrapper for email/calendar data |
| DeletesAsMoves | 0x1E | 0x5E | `5E` | Move deleted items to trash |
| Supported | 0x20 | 0x60 | `60` | Supported features |

### Code Page 2: Email

**Purpose**: Email-specific properties

| Element | Base | +Content | Hex (Content) | Required | Description |
|---------|------|----------|---------------|----------|-------------|
| DateReceived | 0x0F | 0x4F | `4F` | ✅ | ISO 8601 timestamp (UTC) |
| DisplayTo | 0x11 | 0x51 | `51` | ⚠️ | Display-friendly recipient list |
| Importance | 0x12 | 0x52 | `52` | ⚠️ | 0=Low, 1=Normal, 2=High |
| MessageClass | 0x13 | 0x53 | `53` | ✅ | IPM.Note (email), IPM.Appointment, etc |
| Subject | 0x14 | 0x54 | `54` | ✅ | Email subject line |
| Read | 0x15 | 0x55 | `55` | ✅ | 0=unread, 1=read |
| To | 0x16 | 0x56 | `56` | ✅ | Recipient email address |
| Cc | 0x17 | 0x57 | `57` | ⚠️ | CC recipients |
| From | 0x18 | 0x58 | `58` | ✅ | Sender email address |
| ReplyTo | 0x19 | 0x59 | `59` | ⚠️ | Reply-To address |
| InternetCPID | 0x39 | 0x79 | `79` | ⚠️ | Code page (65001=UTF-8) |
| ThreadTopic | 0x35 | 0x75 | `75` | ⚠️ | Thread subject |

### Code Page 17: AirSyncBase

**Purpose**: Body content and MIME handling

| Element | Base | +Content | Hex (Content) | Required | Description |
|---------|------|----------|---------------|----------|-------------|
| Type | 0x06 | 0x46 | `46` | ✅ | 1=PlainText, 2=HTML, 3=RTF, 4=MIME |
| Body | 0x0A | 0x4A | `4A` | ✅ | Container for body content |
| Data | 0x0B | 0x4B | `4B` | ✅ | Actual body text |
| EstimatedDataSize | 0x0C | 0x4C | `4C` | ✅ | Size in bytes |
| Truncated | 0x0D | 0x4D | `4D` | ✅ | 0=full, 1=truncated |
| NativeBodyType | 0x10 | 0x50 | `50` | ⚠️ | Original format |
| Preview | 0x14 | 0x54 | `54` | ⚠️ | Short preview text |

**⚠️ CRITICAL ORDERING** in `<Body>`:
```
<Body>
  <Type>1</Type>                        ← FIRST
  <EstimatedDataSize>512</EstimatedDataSize>  ← SECOND
  <Truncated>0</Truncated>              ← THIRD
  <Data>Email body text...</Data>       ← FOURTH
</Body>
```

**iOS will reject if order is wrong!**

---

## 🔄 Protocol Flow

### 1. OPTIONS (Capability Discovery)

**Request:**
```http
OPTIONS /Microsoft-Server-ActiveSync HTTP/1.1
Host: mail.example.com
MS-ASProtocolVersion: 14.1
```

**Response:**
```http
HTTP/1.1 200 OK
MS-ASProtocolVersions: 14.1
MS-ASProtocolCommands: Sync,FolderSync,GetItemEstimate,MoveItems,...
MS-Server-ActiveSync: 14.1
```

### 2. FolderSync (Get Folder List)

**Request Body (WBXML):**
```
03 01 6A 00           # Header
00 07                 # Switch to FolderHierarchy (CP 7)
56                    # <FolderSync> with content
52 03 30 00 01        # <SyncKey>0</SyncKey>
01                    # </FolderSync>
```

**Response Structure:**
```xml
<FolderSync>
  <Status>1</Status>
  <SyncKey>1</SyncKey>
  <Changes>
    <Count>6</Count>
    <Add>
      <ServerId>1</ServerId>
      <ParentId>0</ParentId>
      <DisplayName>Inbox</DisplayName>
      <Type>2</Type>
    </Add>
    <!-- More folders... -->
  </Changes>
</FolderSync>
```

### 3. Sync - Initial (SyncKey 0→1)

**Request:**
```xml
<Sync>
  <Collections>
    <Collection>
      <SyncKey>0</SyncKey>
      <CollectionId>1</CollectionId>
      <WindowSize>25</WindowSize>
      <Options>
        <FilterType>0</FilterType>
        <BodyPreference>
          <Type>1</Type>
          <TruncationSize>512</TruncationSize>
        </BodyPreference>
      </Options>
    </Collection>
  </Collections>
</Sync>
```

**Response (Minimal - NO ITEMS on initial):**
```xml
<Sync>
  <Collections>
    <Collection>
      <SyncKey>1</SyncKey>
      <CollectionId>1</CollectionId>
      <Status>1</Status>
      <Class>Email</Class>
    </Collection>
  </Collections>
</Sync>
```

**WBXML Bytes:**
```
03 01 6A 00           # Header
00 00                 # Switch to AirSync (CP 0)
45                    # <Sync> with content
5C                    # <Collections> with content
4F                    # <Collection> with content
4B 03 31 00 01        # <SyncKey>1</SyncKey>
52 03 31 00 01        # <CollectionId>1</CollectionId>
4E 03 31 00 01        # <Status>1</Status>
50 03 45 6D 61 69 6C 00 01  # <Class>Email</Class>
01                    # </Collection>
01                    # </Collections>
01                    # </Sync>
```

### 4. Sync - Subsequent (SyncKey 1→2, with items)

**Request:**
```xml
<Sync>
  <Collections>
    <Collection>
      <SyncKey>1</SyncKey>
      <CollectionId>1</CollectionId>
      <GetChanges>1</GetChanges>
      <WindowSize>25</WindowSize>
    </Collection>
  </Collections>
</Sync>
```

**Response (With Email Items):**
```xml
<Sync>
  <Collections>
    <Collection>
      <SyncKey>2</SyncKey>
      <CollectionId>1</CollectionId>
      <Status>1</Status>
      <Class>Email</Class>
      <Commands>
        <Add>
          <ServerId>1:35</ServerId>
          <ApplicationData>
            <!-- Switch to Email CP 2 -->
            <Subject>Test Email</Subject>
            <From>sender@example.com</From>
            <To>recipient@example.com</To>
            <DateReceived>2025-10-03T01:15:00.000Z</DateReceived>
            <Read>0</Read>
            
            <!-- Switch to AirSyncBase CP 17 -->
            <Body>
              <Type>1</Type>
              <EstimatedDataSize>512</EstimatedDataSize>
              <Truncated>0</Truncated>
              <Data>Email body text here...</Data>
            </Body>
          </ApplicationData>
        </Add>
      </Commands>
      <MoreAvailable/>  <!-- If more items exist -->
    </Collection>
  </Collections>
</Sync>
```

---

## 🔧 State Machine Implementation

### Core Concept: Idempotent Resends

**Problem**: iOS/iPhone will retry requests if network is slow or response is delayed. Server MUST send **identical** response for retries.

### State Structure

```python
@dataclass
class SyncState:
    cur_key: str = "0"              # Last ACKed key from client
    next_key: str = "1"             # Key to issue in next response
    pending: Optional[bytes] = None  # Cached WBXML for retry
    cursor: int = 0                  # Pagination position
```

### Key Rules

#### Rule 1: Idempotent Resend
```python
if pending_batch_exists and client_sync_key == current_key:
    # Client is retrying - send SAME cached response
    return cached_wbxml_bytes  # Exact same bytes!
```

#### Rule 2: ACK Detection
```python
if client_sync_key == next_key:
    # Client ACKed! Advance state
    current_key = next_key
    next_key = str(int(next_key) + 1)
    pending = None  # Clear cache
    # Generate NEW batch with new sync key
```

#### Rule 3: Never Spurious Reset
```python
# NEVER do this:
if client_key != server_key:
    sync_key = "0"  # ❌ WRONG! Causes infinite loop

# ALWAYS preserve state:
if unexpected_key:
    # Reset cursor, NOT sync keys
    cursor = 0
    # Log warning, but keep keys intact
```

### State Flow Example

```
Request 1: client_key=0
  → cur_key=0, next_key=1
  → Generate batch, cache WBXML
  → Response: sync_key=1
  
Request 2: client_key=0 (retry!)
  → cur_key=0, next_key=1, pending=<cached>
  → Detect retry (client_key == cur_key)
  → Response: SAME cached WBXML with sync_key=1
  
Request 3: client_key=1 (ACK!)
  → Detect ACK (client_key == next_key)
  → Advance: cur_key=1, next_key=2
  → Clear pending cache
  → Generate NEW batch
  → Response: sync_key=2
```

---

## 🛠️ WBXML Builder Implementation

### Complete Python Implementation

```python
class WBXMLWriter:
    """Minimal WBXML writer for ActiveSync"""
    
    def __init__(self):
        self.buf = bytearray()
        self.current_page = 0xFFFF  # Force initial page switch
    
    def header(self):
        """Write WBXML header"""
        self.buf.extend([0x03, 0x01, 0x6A, 0x00])
    
    def write_byte(self, b: int):
        self.buf.append(b & 0xFF)
    
    def write_str(self, s: str):
        """Write inline string (STR_I)"""
        self.write_byte(0x03)  # STR_I token
        self.buf.extend(s.encode('utf-8'))
        self.write_byte(0x00)  # Null terminator
    
    def page(self, cp: int):
        """Switch code page if needed"""
        if self.current_page != cp:
            self.write_byte(0x00)  # SWITCH_PAGE
            self.write_byte(cp & 0xFF)
            self.current_page = cp
    
    def start(self, tok: int, with_content: bool = True):
        """Start element"""
        self.write_byte((tok | 0x40) if with_content else tok)
    
    def end(self):
        """End element"""
        self.write_byte(0x01)  # END
    
    def bytes(self) -> bytes:
        return bytes(self.buf)


def build_sync_response(sync_key: str, emails: list, 
                        collection_id: str = "1",
                        window_size: int = 25) -> bytes:
    """
    Build complete Sync response WBXML
    
    Args:
        sync_key: NEW sync key to return (e.g. "2")
        emails: List of email dicts
        collection_id: Folder ID
        window_size: Max items to send
    
    Returns:
        WBXML bytes
    """
    w = WBXMLWriter()
    w.header()
    
    # <Sync>
    w.page(0)  # AirSync
    w.start(0x05)  # Sync with content
    
    # <Collections>
    w.start(0x1C)  # Collections with content
    
    # <Collection>
    w.start(0x0F)  # Collection with content
    
    # <SyncKey>
    w.start(0x0B)  # SyncKey with content
    w.write_str(sync_key)
    w.end()
    
    # <CollectionId>
    w.start(0x12)  # CollectionId with content
    w.write_str(collection_id)
    w.end()
    
    # <Status>
    w.start(0x0E)  # Status with content
    w.write_str("1")  # Success
    w.end()
    
    # <Class>
    w.start(0x10)  # Class with content
    w.write_str("Email")
    w.end()
    
    # MoreAvailable (if needed)
    if len(emails) > window_size:
        w.start(0x14, with_content=False)  # Empty tag!
    
    # <Commands>
    if emails:
        w.start(0x16)  # Commands with content
        
        for email in emails[:window_size]:
            # <Add>
            w.start(0x07)  # Add with content
            
            # <ServerId> REQUIRED!
            w.start(0x0D)  # ServerId with content
            w.write_str(f"{collection_id}:{email['id']}")
            w.end()
            
            # <ApplicationData>
            w.start(0x1D)  # ApplicationData with content
            
            # Switch to Email CP
            w.page(2)
            
            # Email properties
            w.start(0x14); w.write_str(email.get('subject', '')); w.end()  # Subject
            w.start(0x18); w.write_str(email.get('from', '')); w.end()  # From
            w.start(0x16); w.write_str(email.get('to', '')); w.end()  # To
            w.start(0x0F); w.write_str(email['date_iso']); w.end()  # DateReceived
            w.start(0x15); w.write_str('1' if email.get('read') else '0'); w.end()  # Read
            
            # Switch to AirSyncBase CP
            w.page(17)
            
            # <Body>
            w.start(0x0A)  # Body with content
            
            # CRITICAL ORDER: Type → EstimatedDataSize → Truncated → Data
            body_text = email.get('body', '')
            body_bytes = body_text.encode('utf-8')
            
            # <Type>
            w.start(0x06)  # Type with content
            w.write_str("1")  # PlainText
            w.end()
            
            # <EstimatedDataSize>
            w.start(0x0C)  # EstimatedDataSize with content
            w.write_str(str(len(body_bytes)))
            w.end()
            
            # <Truncated>
            w.start(0x0D)  # Truncated with content (boolean!)
            w.write_str("0")  # Not truncated
            w.end()
            
            # <Data>
            w.start(0x0B)  # Data with content
            w.write_str(body_text)
            w.end()
            
            w.end()  # </Body>
            
            # Switch back to AirSync
            w.page(0)
            
            w.end()  # </ApplicationData>
            w.end()  # </Add>
        
        w.end()  # </Commands>
    
    w.end()  # </Collection>
    w.end()  # </Collections>
    w.end()  # </Sync>
    
    return w.bytes()
```

---

## ⚠️ Common Pitfalls & Solutions

### 1. Missing `<ServerId>` in `<Add>`

**Symptom**: iOS loops, doesn't download items

**Cause**: `<ServerId>` is REQUIRED but was missing

**Solution**:
```python
# ✅ CORRECT:
<Add>
  <ServerId>1:35</ServerId>  # REQUIRED!
  <ApplicationData>...</ApplicationData>
</Add>

# ❌ WRONG:
<Add>
  <ApplicationData>
    <ServerId>1:35</ServerId>  # Wrong location!
  </ApplicationData>
</Add>
```

### 2. Wrong `<ApplicationData>` Token

**Symptom**: iOS rejects entire response

**Cause**: Used wrong token (0x4F instead of 0x5D)

**Solution**:
```python
# ✅ CORRECT:
ApplicationData = 0x1D  # Base token
w.start(0x1D)  # 0x1D | 0x40 = 0x5D

# ❌ WRONG:
w.start(0x0F)  # This is Collection, not ApplicationData!
```

### 3. `<Body>` Element Ordering

**Symptom**: iOS displays garbled text or rejects email

**Cause**: Wrong order of Type/EstimatedDataSize/Truncated/Data

**Solution**:
```python
# ✅ CORRECT ORDER:
<Body>
  <Type>1</Type>
  <EstimatedDataSize>512</EstimatedDataSize>
  <Truncated>0</Truncated>
  <Data>Body text...</Data>
</Body>

# ❌ WRONG ORDER:
<Body>
  <Data>Body text...</Data>
  <Type>1</Type>  # iOS will reject!
</Body>
```

### 4. `<MoreAvailable/>` Wrong Token

**Symptom**: iOS keeps requesting more items endlessly

**Cause**: Used wrong token or added content flag

**Solution**:
```python
# ✅ CORRECT:
w.start(0x14, with_content=False)  # Empty tag, token 0x14

# ❌ WRONG:
w.start(0x14)  # with_content=True makes it 0x54!
w.start(0x1B)  # Wrong token entirely!
```

### 5. Non-Idempotent Resends

**Symptom**: Server state flips to "0", infinite loop

**Cause**: Generated NEW batch on retry instead of cached

**Solution**:
```python
# ✅ CORRECT:
if pending_batch and client_key == cur_key:
    return pending_batch  # SAME bytes!

# ❌ WRONG:
# Always generate new batch:
batch = generate_new_batch()
return batch  # Different bytes each time!
```

### 6. Invalid SWITCH_PAGE

**Symptom**: iOS rejects response, SyncKey=0 loop

**Cause**: Extra SWITCH_PAGE to CP 0 at start

**Solution**:
```python
# ✅ CORRECT:
03 01 6A 00           # Header
00 00                 # SWITCH_PAGE to CP 0 (first time only)
45                    # <Sync>

# ❌ WRONG:
03 01 6A 00           # Header
00 00 00              # Extra 0x00 byte! Invalid!
45                    # <Sync>
```

### 7. Protocol Version Mismatch

**Symptom**: iOS drops all responses

**Cause**: OPTIONS advertised 16.1 but sent 14.1 format

**Solution**:
```python
# ✅ CORRECT:
# OPTIONS response:
MS-ASProtocolVersions: 14.1  # Only what you support

# Command response:
client_version = request.headers.get("MS-ASProtocolVersion")
response_headers["MS-ASProtocolVersion"] = client_version  # Echo back

# ❌ WRONG:
# OPTIONS: MS-ASProtocolVersions: 14.1,16.0,16.1
# Response: MS-ASProtocolVersion: 14.1
# (Mismatch causes iOS to reject!)
```

---

## ✅ Testing & Verification

### 1. Verify WBXML Header

```python
def check_wbxml_header(wbxml_bytes):
    """Verify WBXML header is correct"""
    assert wbxml_bytes[0] == 0x03, "Version must be 0x03 (WBXML 1.3)"
    assert wbxml_bytes[1] == 0x01, "Public ID must be 0x01 (unknown)"
    assert wbxml_bytes[2] == 0x6A, "Charset must be 0x6A (UTF-8)"
    assert wbxml_bytes[3] == 0x00, "String table must be 0x00 (none)"
    print("✅ Header valid:", wbxml_bytes[:4].hex())
```

### 2. Verify Code Page Switches

```python
def trace_code_pages(wbxml_bytes):
    """Track code page switches in WBXML"""
    current_page = None
    i = 4  # Skip header
    
    while i < len(wbxml_bytes):
        if wbxml_bytes[i] == 0x00:  # SWITCH_PAGE
            current_page = wbxml_bytes[i+1]
            print(f"Page switch to CP {current_page}")
            i += 2
        else:
            i += 1
```

### 3. Manual WBXML Inspection

```bash
# Dump first 100 bytes
xxd -l 100 response.wbxml

# Expected pattern:
# 00000000: 0301 6a00 0000 455c 4f4b 0331 0001 5203  ..j...E\OK.1..R.
#           ^^^^^^^^ ^^^^ ^^^^ ^^^^                    
#           Header   SW   CP0  Sync
```

### 4. Test with iPhone

```
1. Delete Exchange account
2. Re-add with fresh credentials
3. Watch logs:
   - SyncKey progression: 0→1→2→3...
   - No loops or resets to 0
   - Messages appear in Mail app
```

### 5. Verify State Machine

```python
# Test idempotent resend
def test_idempotent_resend():
    store = SyncStateStore()
    
    # First request
    batch1 = store.prepare_batch(
        user="test@example.com",
        device_id="TEST123",
        collection_id="1",
        client_sync_key="0",
        emails=test_emails,
        window_size=5
    )
    
    # Retry (same client_sync_key)
    batch2 = store.prepare_batch(
        user="test@example.com",
        device_id="TEST123",
        collection_id="1",
        client_sync_key="0",  # SAME!
        emails=test_emails,
        window_size=5
    )
    
    # Must be IDENTICAL bytes
    assert batch1.wbxml == batch2.wbxml
    assert batch1.response_sync_key == batch2.response_sync_key
    print("✅ Idempotent resend verified")
```

---

## 📚 Microsoft Specifications Reference

### Core Specifications

1. **[MS-ASCMD]**: ActiveSync Command Reference Protocol
   - Section 2.2.2: Sync Command
   - Section 2.2.3.166.2: SyncKey Element
   - Section 2.2.3.6: Add Element
   - Section 2.2.3.10: ApplicationData Element

2. **[MS-ASWBXML]**: ActiveSync WBXML Algorithm
   - Section 2.1.1.5.7.1: Code Pages
   - Section 2.1.2.1.1: AirSync Code Page (0)
   - Section 2.1.2.1.3: Email Code Page (2)
   - Section 2.1.2.1.18: AirSyncBase Code Page (17)

3. **[MS-ASDTYPE]**: ActiveSync Data Types
   - Section 2.6: DateTime Format
   - Section 2.7: Integer Format
   - Section 2.8: String Format

4. **[MS-ASPROV]**: ActiveSync Provisioning Protocol
   - Section 2.2.2: Provision Command
   - Section 2.2.3: Policy Types

### Z-Push References

1. **Z-Push Source Code**: https://github.com/Z-Push/Z-Push
   - `lib/request/sync.php`: Sync command implementation
   - `lib/core/statemanager.php`: SyncKey management
   - `lib/wbxml/wbxmldefs.php`: Token definitions

2. **Grommunio-Sync**: https://github.com/grommunio/grommunio-sync
   - Modern fork of Z-Push
   - Active maintenance
   - iOS-tested implementation

### Token Reference Tables

**WAP-192-WBXML Specification**:
- STR_I (0x03): Inline string
- END (0x01): Close element
- SWITCH_PAGE (0x00): Change code page

**Content Flag**: `0x40`
- All elements can have content flag set
- `token | 0x40` = element with children/text

---

## 🎯 Success Criteria

✅ **You've successfully implemented ActiveSync when**:

1. iPhone sends `SyncKey=0`, server responds with `SyncKey=1`
2. iPhone sends `SyncKey=1`, server responds with `SyncKey=2` + items
3. iPhone displays emails in Mail app
4. SyncKey progresses: `0→1→2→3→4...` (no loops!)
5. Retry requests get identical responses (idempotent)
6. MoreAvailable pagination works correctly
7. New emails sync automatically

---

## 📝 Implementation Checklist

When implementing from scratch, verify:

- [ ] WBXML header: `03 01 6A 00`
- [ ] Code page switches: `00 <page_number>`
- [ ] Content flags: token | 0x40 for elements with children
- [ ] AirSync tokens (CP 0): Sync, Collections, Collection, Commands, Add, ServerId, ApplicationData
- [ ] Email tokens (CP 2): Subject, From, To, DateReceived, Read
- [ ] AirSyncBase tokens (CP 17): Body, Type, EstimatedDataSize, Truncated, Data
- [ ] Body element ordering: Type → EstimatedDataSize → Truncated → Data
- [ ] ServerId inside Add element (NOT inside ApplicationData)
- [ ] ApplicationData token: 0x1D (not 0x0F)
- [ ] MoreAvailable as empty tag (0x14, not 0x54)
- [ ] State machine: idempotent resends
- [ ] State machine: never spurious reset
- [ ] Protocol version: echo client's version
- [ ] Status codes: 1=success

---

**Document Version**: 1.0  
**Last Updated**: October 3, 2025  
**Status**: Production-Tested with iPhone/iOS

**This document contains everything needed to implement ActiveSync from scratch without external dependencies.**

