# 365 Email System - Production ActiveSync Server

![Status](https://img.shields.io/badge/status-production-green)
![ActiveSync](https://img.shields.io/badge/ActiveSync-14.1-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

**A production-ready Microsoft Exchange ActiveSync server implementation with full iPhone/iOS support.**

## 🎯 Features

### ✅ **Fully Operational ActiveSync**
- **Email Sync**: Complete WBXML-compliant email synchronization
- **iOS Support**: Tested and working with iPhone Mail app
- **Z-Push Compatible**: State machine based on Z-Push/Grommunio-Sync
- **Idempotent Resends**: Proper retry handling per ActiveSync spec
- **Pagination**: WindowSize enforcement with MoreAvailable tag

### 📧 **Email System**
- **SMTP Server**: Internal SMTP on ports 25, 587, 465
- **Email Storage**: SQLite/PostgreSQL with full relationship tracking
- **Queue System**: Background processing for reliable delivery
- **MX Lookup**: Automatic external email routing
- **Web Interface**: OWA-style webmail (Outlook Web Access)

### 🔐 **Security & Authentication**
- **Modern Authentication**: OAuth2 with Microsoft-compatible endpoints
- **Basic Auth**: Legacy device support
- **SSL/TLS**: Automatic certificate generation
- **Device Provisioning**: MS-ASPROV compliant policies

### 🌐 **Protocols Supported**
- **ActiveSync 14.1**: Full implementation (MS-ASCMD, MS-ASWBXML, MS-ASDTYPE)
- **Autodiscover**: Automatic client configuration (MS-ASCMD, Outlook)
- **MAPI/HTTP**: Outlook 2016+ support (partial)
- **SMTP**: Full RFC-compliant server

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- SSL certificates (auto-generated or custom)

### 1. Clone Repository
```bash
git clone https://github.com/shtrumj/365_preorder_with-oprational_activesync.git
cd 365_preorder_with-oprational_activesync
```

### 2. Configuration
```bash
# Copy environment template
cp config.example.env .env

# Edit .env with your settings
nano .env
```

**Required settings:**
```env
# MUST CHANGE: Generate with python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-secret-key-change-this-in-production

# Your domain
DOMAIN=mail.yourdomain.com
HOSTNAME=mail.yourdomain.com

# Optional: Only if using Cloudflare DNS for SSL
CLOUDFLARE_API_TOKEN=your_cloudflare_token_here
ALT_NAMES=autodiscover.yourdomain.com,owa.yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
```

**Note**: All environment variables in docker-compose.yml now have sensible defaults. Only override in `.env` what you need to customize.

### 3. Start Services
```bash
# Build and start
docker-compose up -d

# Check health
docker-compose ps
docker-compose logs -f email-system
```

### 4. Create Admin User
```bash
# Inside container
docker exec -it 365-email-system python -c "
from app.database import SessionLocal, User
from passlib.context import CryptContext

db = SessionLocal()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

user = User(
    email='admin@yourdomain.com',
    hashed_password=pwd_context.hash('your_password'),
    is_admin=True
)
db.add(user)
db.commit()
print(f'Created: {user.email}')
"
```

---

## 📱 **iPhone/iOS Setup**

### Add Exchange Account

1. **Settings** → **Mail** → **Accounts** → **Add Account** → **Exchange**

2. **Enter Details:**
   - **Email**: your@yourdomain.com
   - **Description**: My Mail Server
   - **Server**: mail.yourdomain.com
   - **Domain**: (leave blank)
   - **Username**: your@yourdomain.com
   - **Password**: your_password

3. **Sign In** - iPhone will auto-discover settings

4. **Enable Sync:**
   - ✅ Mail
   - ✅ Contacts (if enabled)
   - ✅ Calendars (if enabled)

### Troubleshooting iPhone Sync

```bash
# Watch real-time sync
tail -f logs/activesync/activesync.log | jq .

# Reset device state (if stuck)
docker exec -it 365-email-system python reset_activesync_state.py --list
docker exec -it 365-email-system python reset_activesync_state.py --user your@email.com --device DEVICE_ID
```

---

## 🏗️ **Architecture**

### Directory Structure
```
365_preorder_with-oprational_activesync/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration
│   ├── database.py                # SQLAlchemy models
│   ├── auth.py                    # Authentication
│   │
│   ├── routers/                   # API endpoints
│   │   ├── activesync.py          # ActiveSync protocol handler
│   │   ├── autodiscover.py        # Autodiscover endpoint
│   │   ├── owa.py                 # Webmail interface
│   │   ├── mapi.py                # MAPI/HTTP (Outlook)
│   │   └── ...
│   │
│   ├── services/                  # Business logic
│   │   ├── email_service.py       # Email operations
│   │   ├── calendar_service.py    # Calendar sync
│   │   └── contact_service.py     # Contact sync
│   │
│   ├── activesync/               # ActiveSync core (Z-Push style)
│   │   ├── minimal_sync_wbxml_expert.py  # WBXML builder
│   │   ├── sync_state.py          # State machine
│   │   └── sync_adapter.py        # DB integration
│   │
│   ├── smtp_server.py             # SMTP server
│   ├── smtp_client.py             # Outbound SMTP
│   ├── email_queue.py             # Queue processor
│   └── ...
│
├── docker-compose.yml             # Docker orchestration
├── Dockerfile                     # Container image
├── requirements.txt               # Python dependencies
├── nginx/                         # Reverse proxy config
├── logs/                          # Application logs
└── README.md                      # This file
```

### Key Components

#### 1. **ActiveSync State Machine** (`app/activesync/`)
Based on Z-Push/Grommunio-Sync implementation:
- **Idempotent resends**: Same batch for retry requests
- **SyncKey management**: Proper `cur_key` → `next_key` progression
- **Pagination**: Cursor-based with `MoreAvailable` flag
- **Spec-compliant WBXML**: Correct tokens per MS-ASWBXML

#### 2. **Email System** (`app/`)
- **Internal routing**: User-to-user emails stored locally
- **External routing**: MX lookup for external domains
- **Queue processing**: Background workers for reliability
- **Web interface**: OWA-style HTML email client

#### 3. **SMTP Services** (`app/smtp_*.py`)
- **Port 25**: External mail receipt (MTA)
- **Port 587**: Submission with STARTTLS (MSA)
- **Port 465**: Submission with implicit TLS (deprecated but supported)

---

## 🔧 **Development**

### Local Development Setup

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (if any)
# alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing ActiveSync

```bash
# Test OPTIONS (discover capabilities)
curl -X OPTIONS https://mail.yourdomain.com/Microsoft-Server-ActiveSync \
  -u "user@domain.com:password" \
  -H "MS-ASProtocolVersion: 14.1"

# Test FolderSync (get folder list)
curl -X POST https://mail.yourdomain.com/Microsoft-Server-ActiveSync?Cmd=FolderSync \
  -u "user@domain.com:password" \
  -H "MS-ASProtocolVersion: 14.1" \
  -H "Content-Type: application/vnd.ms-sync.wbxml" \
  --data-binary @foldersync_request.wbxml
```

### Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker-compose restart email-system

# Watch ActiveSync logs
tail -f logs/activesync/activesync.log | jq -r '"\(.ts) | \(.event) | \(.message // "")"'

# WBXML hex dump
tail -f logs/activesync/activesync.log | jq -r 'select(.wbxml_hex) | .wbxml_hex'
```

---

## 📚 **API Documentation**

### ActiveSync Endpoints

#### **OPTIONS** - Capabilities Discovery
```http
OPTIONS /Microsoft-Server-ActiveSync HTTP/1.1
Host: mail.yourdomain.com
MS-ASProtocolVersion: 14.1
```

**Response:**
```http
MS-ASProtocolVersions: 14.1
MS-ASProtocolCommands: Sync,FolderSync,GetItemEstimate,MoveItems,...
```

#### **Sync** - Email Synchronization
```http
POST /Microsoft-Server-ActiveSync?Cmd=Sync&User=user@domain.com&DeviceId=DEVICE123&DeviceType=iPhone HTTP/1.1
Host: mail.yourdomain.com
MS-ASProtocolVersion: 14.1
Content-Type: application/vnd.ms-sync.wbxml

[WBXML Request Body]
```

**SyncKey Flow:**
1. Client sends `SyncKey=0` (initial sync)
2. Server responds `SyncKey=1` (folder structure established)
3. Client sends `SyncKey=1` (ready for items)
4. Server responds `SyncKey=2` + email items
5. Repeat: `2→3→4→5...` (incremental sync)

---

## 🛠️ **Admin Tools**

### Reset ActiveSync State (Z-Push Style)

```bash
# List all states
python reset_activesync_state.py --list

# Reset specific device
python reset_activesync_state.py \
  --user user@domain.com \
  --device DEVICE123

# Reset all devices for user
python reset_activesync_state.py \
  --user user@domain.com \
  --all-devices
```

### Database Management

```bash
# SQLite backup
sqlite3 email_system.db ".backup email_system_backup.db"

# Query users
sqlite3 email_system.db "SELECT email, is_admin FROM users;"

# Reset password
python reset_password.py user@domain.com new_password
```

---

## 📖 **Protocol References**

### Microsoft Specifications
- **[MS-ASCMD]**: ActiveSync Command Reference Protocol
- **[MS-ASWBXML]**: ActiveSync WBXML Algorithm
- **[MS-ASDTYPE]**: ActiveSync Data Types
- **[MS-ASPROV]**: ActiveSync Provisioning Protocol
- **[MS-ASHTTP]**: ActiveSync HTTP Protocol

### Open Source References
- **Z-Push**: PHP ActiveSync implementation (http://z-push.org/)
- **Grommunio-Sync**: Modern fork of Z-Push (https://github.com/grommunio/grommunio-sync)
- **Dovecot**: IMAP/POP3 server (for architecture reference)

---

## 🐛 **Known Issues & Limitations**

### Current Limitations
- ⚠️ Calendar sync: Partial implementation
- ⚠️ Contacts sync: Partial implementation
- ⚠️ Search: Not yet implemented
- ⚠️ Push notifications: Polling only (no HTTPS callback)

### Tested Clients
- ✅ iPhone Mail (iOS 16.x, 17.x, 18.x)
- ✅ Android Email (basic)
- ⚠️ Outlook 2016+ (MAPI/HTTP partial)
- ⚠️ Windows Mail: Not tested

---

## 📝 **License**

MIT License - See LICENSE file for details

---

## 🙏 **Acknowledgments**

- **Z-Push/Grommunio-Sync**: For the reference ActiveSync implementation
- **Microsoft**: For (eventually) documenting the protocol
- **Community Contributors**: For testing and feedback

---

## 📞 **Support**

- **Issues**: https://github.com/shtrumj/365_preorder_with-oprational_activesync/issues
- **Discussions**: https://github.com/shtrumj/365_preorder_with-oprational_activesync/discussions
- **Email**: support@yourdomain.com

---

**Built with ❤️ for the open-source community**

*Last Updated: October 3, 2025*

