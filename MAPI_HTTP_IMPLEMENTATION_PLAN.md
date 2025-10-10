# MAPI/HTTP Implementation Plan

**Status:** 🚧 **FOUNDATIONAL PHASE** 🚧  
**Estimated Completion:** 6-12 months  
**Complexity:** EXTREME (50,000+ LOC)

---

## Overview

MAPI/HTTP is Microsoft's modern protocol for Outlook Desktop to communicate with Exchange servers. It replaces the legacy MAPI/RPC protocol with a RESTful HTTP-based approach.

**Key Specifications:**
- [MS-OXCMAPIHTTP] - MAPI/HTTP Protocol
- [MS-OXCROPS] - Remote Operations
- [MS-OXCFOLD] - Folder Operations
- [MS-OXCMSG] - Message Operations
- [MS-OXCDATA] - Data Structures
- [MS-OXCPRPT] - Property Operations
- 50+ additional MS-OX* specifications

---

## Architecture

### Phase 1: Core Infrastructure (Weeks 1-4)

**1.1 MAPI/HTTP Endpoint**
- `/mapi/emsmdb/` - Mailbox endpoint
- `/mapi/nspi/` - Address book endpoint  
- Request/Response serialization
- Session management
- Cookie handling

**1.2 Binary Serialization**
- MAPI property encoding/decoding
- ROP (Remote Operations) buffer parsing
- Multi-value property handling
- Binary stream processing

**1.3 Data Models**
- Folders (Inbox, Sent, Drafts, etc.)
- Messages (Email objects)
- Attachments
- Properties (MAPI property tags)
- Permissions and ACLs

### Phase 2: Core Operations (Weeks 5-12)

**2.1 Session Management**
- Connect/Disconnect
- Session context
- Notification subscriptions
- Idle timeout handling

**2.2 Folder Operations**
- GetHierarchy (folder tree)
- GetContentsTable (folder contents)
- CreateFolder
- DeleteFolder
- MoveFolder

**2.3 Message Operations**
- OpenMessage
- CreateMessage
- SaveMessage
- DeleteMessage
- MoveMessage
- CopyMessage

**2.4 Property Operations**
- GetProps (read properties)
- SetProps (write properties)
- DeleteProps
- CopyProps

### Phase 3: Advanced Features (Weeks 13-24)

**3.1 Search and Filtering**
- Content indexing
- Search folders
- Restriction parsing
- Sort orders

**3.2 Attachments**
- Inline attachments
- File attachments
- Attachment streaming

**3.3 Calendar Integration**
- Appointment objects
- Meeting requests
- Recurring events
- Free/busy lookup

**3.4 Contacts and Address Book**
- Contact objects
- Distribution lists
- NSPI (Name Service Provider)
- Address book hierarchy

---

## Protocol Flow

### 1. Connection Establishment

```
Client                          Server
  |                                |
  |--- POST /mapi/emsmdb/?Cmd=Connect
  |    X-RequestType: Connect      |
  |    X-ClientInfo: <version>     |
  |    Body: <ConnectRequest>      |
  |                                |
  |    <-- 200 OK                  |
  |        Set-Cookie: MapiContext=<context>
  |        Body: <ConnectResponse> |
```

### 2. Execute ROP Operations

```
Client                          Server
  |                                |
  |--- POST /mapi/emsmdb/?Cmd=Execute
  |    Cookie: MapiContext=<ctx>   |
  |    X-RequestType: Execute      |
  |    Body: <ExecuteRequest>      |
  |      - RopBuffer[]             |
  |      - MaxRopOut               |
  |      - AuxIn[]                 |
  |                                |
  |    <-- 200 OK                  |
  |        Body: <ExecuteResponse> |
  |          - RopBuffer[]         |
  |          - AuxOut[]            |
```

### 3. Disconnect

```
Client                          Server
  |                                |
  |--- POST /mapi/emsmdb/?Cmd=Disconnect
  |    Cookie: MapiContext=<ctx>   |
  |    X-RequestType: Disconnect   |
  |                                |
  |    <-- 200 OK                  |
```

---

## MAPI Property System

### Core Property Tags

```python
# Property types
PT_NULL        = 0x0001  # Null
PT_I2          = 0x0002  # 16-bit integer
PT_LONG        = 0x0003  # 32-bit integer
PT_BOOLEAN     = 0x000B  # Boolean
PT_STRING8     = 0x001E  # 8-bit string
PT_UNICODE     = 0x001F  # Unicode string
PT_SYSTIME     = 0x0040  # FILETIME
PT_BINARY      = 0x0102  # Binary data

# Common properties
PR_DISPLAY_NAME         = 0x3001001F  # Display name
PR_SUBJECT              = 0x0037001F  # Email subject
PR_MESSAGE_CLASS        = 0x001A001F  # Message class (IPM.Note, etc.)
PR_BODY                 = 0x1000001F  # Plain text body
PR_HTML                 = 0x10130102  # HTML body
PR_SENDER_NAME          = 0x0C1A001F  # Sender name
PR_SENDER_EMAIL_ADDRESS = 0x0C1F001F  # Sender email
```

### Property Encoding

```
Property Structure:
  - Property Tag (4 bytes)
  - Property Type (2 bytes)
  - Property ID (2 bytes)
  - Value Length (4 bytes)
  - Value Data (variable)
```

---

## ROP Operations

### Common ROPs

| ROP ID | Name | Description |
|--------|------|-------------|
| 0x01 | RopRelease | Release an object |
| 0x07 | RopGetPropsSpecific | Get specific properties |
| 0x0A | RopSetProperties | Set properties |
| 0x0F | RopOpenFolder | Open a folder |
| 0x10 | RopCreateFolder | Create a folder |
| 0x12 | RopGetContentsTable | Get folder contents |
| 0x1E | RopSaveChangesMessage | Save message |
| 0x2E | RopOpenMessage | Open a message |
| 0x32 | RopCreateMessage | Create a message |

### ROP Buffer Format

```
ROP Buffer:
  - ROP Count (2 bytes)
  - ROP Size (2 bytes)
  - ROP Array (variable)
    - ROP ID (1 byte)
    - ROP Size (1 byte)
    - ROP Data (variable)
```

---

## Data Structures

### Folder Object

```python
class MapiFolder:
    folder_id: int
    parent_folder_id: int
    display_name: str
    folder_class: str  # IPF.Note, IPF.Contact, etc.
    content_count: int
    unread_count: int
    has_subfolders: bool
    properties: Dict[int, Any]
```

### Message Object

```python
class MapiMessage:
    message_id: int
    folder_id: int
    subject: str
    body: str
    html_body: str
    sender_name: str
    sender_email: str
    recipients: List[Recipient]
    attachments: List[Attachment]
    message_class: str  # IPM.Note, IPM.Appointment, etc.
    received_time: datetime
    properties: Dict[int, Any]
```

### Attachment Object

```python
class MapiAttachment:
    attachment_id: int
    filename: str
    mime_type: str
    size: int
    data: bytes
    is_inline: bool
    content_id: str
```

---

## Database Schema Changes Needed

### New Tables

```sql
-- MAPI Sessions
CREATE TABLE mapi_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    context_handle BLOB,
    created_at TIMESTAMP,
    last_activity TIMESTAMP,
    expires_at TIMESTAMP
);

-- MAPI Objects (handles)
CREATE TABLE mapi_objects (
    object_id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES mapi_sessions(session_id),
    object_type VARCHAR(32),  -- folder, message, attachment
    entity_id INTEGER,  -- references emails.id, folders, etc.
    handle INTEGER,
    properties JSONB
);

-- MAPI Subscriptions (notifications)
CREATE TABLE mapi_subscriptions (
    subscription_id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES mapi_sessions(session_id),
    folder_id INTEGER,
    notification_types INTEGER,  -- bitmask
    created_at TIMESTAMP
);
```

---

## Implementation Phases

### ✅ Phase 0: Foundation (Week 1)
- [x] Architecture documentation
- [ ] Basic endpoint structure
- [ ] Session management
- [ ] Binary serialization framework

### 🚧 Phase 1: Core Protocol (Weeks 2-8)
- [ ] Connect/Disconnect
- [ ] Execute ROP handler
- [ ] Folder hierarchy
- [ ] Message listing
- [ ] Property system

### 📅 Phase 2: Operations (Weeks 9-16)
- [ ] Create/Delete folders
- [ ] Create/Send messages
- [ ] Read/Write properties
- [ ] Attachments

### 📅 Phase 3: Advanced (Weeks 17-24)
- [ ] Search and filtering
- [ ] Calendar integration
- [ ] Contacts/Address book
- [ ] Shared folders

### 📅 Phase 4: Optimization (Weeks 25-28)
- [ ] Performance tuning
- [ ] Caching layer
- [ ] Connection pooling
- [ ] Load testing

---

## Required Dependencies

```python
# requirements.txt additions
mapi-struct==1.0.0      # MAPI binary structures
pytz>=2023.3            # Timezone handling
bitstring>=4.0.0        # Binary manipulation
```

---

## Testing Strategy

### Unit Tests
- Property encoding/decoding
- ROP parsing
- Folder operations
- Message operations

### Integration Tests
- Outlook 2019/2021 compatibility
- Full sync workflow
- Multi-folder scenarios
- Large message handling

### Performance Tests
- 10,000+ messages
- Concurrent sessions
- Large attachments
- Search performance

---

## Security Considerations

1. **Authentication**
   - Basic Auth over HTTPS
   - OAuth 2.0 support
   - Session token validation

2. **Authorization**
   - Folder permissions
   - Delegate access
   - Shared mailbox access

3. **Data Protection**
   - TLS 1.2+ required
   - Session encryption
   - Audit logging

---

## Known Limitations

### Current Implementation (MAPI/HTTP)
- ❌ No support yet (0% complete)
- ✅ Basic endpoint structure created
- 📅 6-12 months to full implementation

### Recommended Alternative
- ✅ **Use IMAP/SMTP for Outlook Desktop**
- ✅ Already implemented and working
- ✅ Native Outlook support
- ✅ Zero additional development

---

## Resources

### Microsoft Documentation
- [MS-OXCMAPIHTTP] - MAPI/HTTP Transport
- [MS-OXCROPS] - Remote Operations
- [MS-OXCFOLD] - Folder Operations
- [MS-OXCMSG] - Message Operations

### Reference Implementations
- Kopano Core (C++)
- Grommunio Gromox (C++)
- Exchange Server (closed source)

---

## Conclusion

**MAPI/HTTP is a MASSIVE undertaking** requiring:
- 6-12 months full-time development
- 50,000+ lines of code
- Deep Exchange protocol expertise
- Extensive testing

**Recommendation:** Use IMAP/SMTP for Outlook Desktop unless Exchange-exclusive features (shared calendars, public folders, etc.) are absolutely required.

---

**Status:** 🏗️ Foundation created, awaiting decision on full implementation

_Last Updated: 2025-10-10_

