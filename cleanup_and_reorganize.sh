#!/bin/bash
set -e

echo "🧹 Cleaning up and reorganizing codebase..."
echo ""

# Create backup
echo "📦 Creating backup..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "../$BACKUP_DIR"
cp -r . "../$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Backup created at ../$BACKUP_DIR"
echo ""

# Remove old/experimental WBXML files
echo "🗑️  Removing old/experimental files..."
rm -f app/iphone_wbxml.py
rm -f app/ultra_minimal_iphone_wbxml.py
rm -f app/wbxml_encoder_grommunio.py
rm -f app/zpush_wbxml.py
rm -f app/minimal_wbxml.py
rm -f app/simple_wbxml.py
rm -f app/simple_wbxml_response.py
rm -f app/wbxml_converter.py
rm -f app/wbxml_encoder.py
rm -f app/wbxml_encoder_v2.py
rm -f app/minimal_sync_wbxml.py.old
echo "✅ Removed old WBXML files"

# Remove test/debug/analysis scripts
echo "🗑️  Removing test/debug scripts..."
rm -f analyze_*.py
rm -f compare_*.py
rm -f debug_*.py
rm -f diagnose_*.py
rm -f test_*.py
rm -f check_dns_records.py
rm -f migrate_*.py
echo "✅ Removed test/analysis scripts"

# Remove old documentation
echo "🗑️  Removing old documentation..."
rm -f *_OLD.md
rm -f *_BACKUP.md
rm -f CRITICAL_FIX_*.md
rm -f WBXML_REJECTED_*.md
rm -f z_push_res.md
echo "✅ Removed old documentation"

# Remove test result files
echo "🗑️  Removing test results..."
rm -f *_test_results.json
rm -f outlook_diagnostic_report.json
rm -f outlook_troubleshooting_report_*.txt
echo "✅ Removed test results"

# Remove temporary files
echo "🗑️  Removing temporary files..."
rm -f cookies.txt
rm -f headers.txt
rm -f response.html
rm -f test_email.html
rm -f *.reg
rm -f get-pip.py
echo "✅ Removed temporary files"

# Create proper directory structure for ActiveSync
echo "📁 Creating clean directory structure..."
mkdir -p app/activesync
echo "✅ Directory structure created"

# Move ActiveSync files to proper location
echo "📦 Organizing ActiveSync files..."
if [ -f "app/minimal_sync_wbxml_expert.py" ]; then
    mv app/minimal_sync_wbxml_expert.py app/activesync/wbxml_builder.py
    echo "  ✅ Moved wbxml_builder.py"
fi

if [ -f "app/sync_state.py" ]; then
    mv app/sync_state.py app/activesync/state_machine.py
    echo "  ✅ Moved state_machine.py"
fi

if [ -f "app/sync_wbxml_adapter.py" ]; then
    mv app/sync_wbxml_adapter.py app/activesync/adapter.py
    echo "  ✅ Moved adapter.py"
fi

# Create __init__.py for activesync module
cat > app/activesync/__init__.py << 'EOF'
"""
ActiveSync Protocol Implementation

Z-Push/Grommunio-Sync compatible implementation with:
- Spec-compliant WBXML encoding (MS-ASWBXML)
- Idempotent state machine (proper retry handling)
- Full iOS/iPhone support
"""

from .wbxml_builder import create_sync_response_wbxml, SyncBatch
from .state_machine import SyncStateStore
from .adapter import sync_prepare_batch, convert_db_email_to_dict

__all__ = [
    'create_sync_response_wbxml',
    'SyncBatch',
    'SyncStateStore',
    'sync_prepare_batch',
    'convert_db_email_to_dict',
]
EOF
echo "✅ ActiveSync module organized"

# Update README
echo "📝 Updating README..."
if [ -f "README_NEW.md" ]; then
    mv README_NEW.md README.md
    echo "✅ README updated"
fi

# Update .gitignore
echo "📝 Updating .gitignore..."
if [ -f ".gitignore_new" ]; then
    mv .gitignore_new .gitignore
    echo "✅ .gitignore updated"
fi

# Create ARCHITECTURE.md
echo "📝 Creating ARCHITECTURE.md..."
cat > ARCHITECTURE.md << 'EOF'
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
EOF
echo "✅ ARCHITECTURE.md created"

# Clean up old scripts directory if empty
if [ -d "test_scripts" ] && [ -z "$(ls -A test_scripts)" ]; then
    rmdir test_scripts
    echo "✅ Removed empty test_scripts directory"
fi

echo ""
echo "✨ Cleanup complete!"
echo ""
echo "📊 Summary:"
echo "  • Removed old/experimental WBXML files"
echo "  • Removed test/debug/analysis scripts"
echo "  • Organized ActiveSync into app/activesync/"
echo "  • Updated README.md and .gitignore"
echo "  • Created ARCHITECTURE.md"
echo ""
echo "📦 Backup available at: ../$BACKUP_DIR"
echo ""
echo "🎯 Next steps:"
echo "  1. Review changes: git status"
echo "  2. Test the system: docker-compose up -d"
echo "  3. Commit: git add . && git commit -m 'Initial clean commit'"
echo "  4. Push: git push new-origin main"

