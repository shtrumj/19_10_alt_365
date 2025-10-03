# System Architecture

## Overview

365 Email System is a production-ready Microsoft Exchange ActiveSync server implementation designed for full compatibility with iOS/iPhone Mail clients while maintaining extensibility for other email protocols.

## Core Components

### 1. ActiveSync Protocol (`app/activesync/`)

#### State Machine (`state_machine.py`)
- **Purpose**: Manages SyncKey progression and idempotent resends
- **Key Concepts**:
  - `cur_key`: Last ACKed sync key from client
  - `next_key`: Sync key to issue in next response
  - `pending`: Cached batch for retry requests
  - `cursor`: Pagination position
  
**State Flow:**
```
Client Request → State Check → Generate/Resend → Update State → Response
```

#### WBXML Builder (`wbxml_builder.py`)
- **Purpose**: Generates MS-ASWBXML compliant binary XML
- **Codepages Used**:
  - AirSync (CP 0): Structure elements
  - Email (CP 2): Email properties
  - AirSyncBase (CP 17): Body content

#### Adapter (`adapter.py`)
- **Purpose**: Bridges SQLAlchemy models to WBXML format
- **Functions**:
  - `convert_db_email_to_dict()`: Model → Dict
  - `sync_prepare_batch()`: High-level batch preparation

### 2. Email System (`app/`)

#### Database (`database.py`)
- **Models**: User, Email, Folder, ActiveSyncState
- **Relationships**: Proper foreign keys and cascade deletes
- **Indexes**: Optimized for ActiveSync queries

#### SMTP Services
- **smtp_server.py**: Inbound mail (ports 25, 587, 465)
- **smtp_client.py**: Outbound mail (MX lookup + delivery)
- **email_queue.py**: Background processing queue

#### Email Service (`email_service.py`)
- **Operations**: CRUD for emails, folders, search
- **Routing**: Internal vs external delivery logic

### 3. API Endpoints (`app/routers/`)

#### ActiveSync Router (`activesync.py`)
- **Commands Supported**:
  - OPTIONS: Capability discovery
  - FolderSync: Folder hierarchy
  - Sync: Email synchronization
  - GetItemEstimate: Count of changes
  - Provision: Device policy
  - MoveItems: Folder operations

#### Autodiscover (`autodiscover.py`)
- **Protocols**: XML, JSON, POX
- **Clients**: Outlook, iPhone, Android

#### OWA (`owa.py`)
- **Features**: Webmail interface
- **Compatibility**: Modern browsers

### 4. Infrastructure

#### Docker Setup
- **Containers**: email-system, nginx, certbot
- **Network**: Isolated docker network
- **Volumes**: Persistent data, logs, SSL certs

#### Nginx Proxy
- **TLS Termination**: SSL/TLS for all traffic
- **Reverse Proxy**: Routes to FastAPI backend
- **Headers**: ActiveSync protocol headers preserved

## Data Flow

### Email Sync Flow (ActiveSync)

```
iPhone → OPTIONS → Server (capability check)
iPhone → FolderSync → Server (get folder list)
iPhone → Sync (SyncKey=0) → Server (initial sync)
Server → SyncKey=1 (minimal response)
iPhone → Sync (SyncKey=1) → Server (request items)
Server → SyncKey=2 + emails (batch of items)
iPhone → Sync (SyncKey=2) → Server (next batch)
...
```

### Email Delivery Flow (SMTP)

```
External MTA → Port 25 → smtp_server.py
  → Parse & Validate → email_queue.py
    → Background Worker → database.py
      → Store Email → Trigger ActiveSync Sync
```

## Security Architecture

### Authentication
1. **Basic Auth**: Username/password (legacy support)
2. **OAuth2**: Modern authentication (Microsoft-compatible)
3. **Device Provisioning**: Policy enforcement (MS-ASPROV)

### Authorization
- User-level: Own emails only
- Admin-level: System configuration
- Device-level: Per-device state isolation

### TLS/SSL
- **Automatic**: certbot with Let's Encrypt
- **Manual**: Custom certificates supported
- **Protocols**: TLS 1.2, TLS 1.3

## Scalability Considerations

### Current Implementation
- **Database**: SQLite (suitable for < 100 users)
- **State Storage**: In-memory (single-instance)
- **Queue**: Single-threaded background worker

### Future Enhancements
- **Database**: PostgreSQL with connection pooling
- **State Storage**: Redis for multi-instance
- **Queue**: Celery for distributed workers
- **Caching**: Redis for email metadata

## Monitoring & Logging

### Log Files
- `logs/activesync/activesync.log`: Protocol-level events
- `logs/email_processing.log`: Email delivery
- `logs/smtp/`: SMTP transactions
- `logs/web/`: HTTP access logs

### Metrics (Future)
- ActiveSync sync count
- Email delivery rate
- Error rates by protocol
- Client distribution (iOS, Android, etc.)

## References

- **ActiveSync**: Microsoft MS-ASCMD, MS-ASWBXML specs
- **Z-Push**: PHP reference implementation
- **Grommunio-Sync**: Modern Z-Push fork
- **FastAPI**: Web framework documentation
- **SQLAlchemy**: ORM documentation
