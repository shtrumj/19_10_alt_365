# 365 Email System

A Microsoft 365-like email system built with FastAPI, SQLite, Jinja2 templates, SMTP server, and ActiveSync support.

## Features

- **FastAPI Backend**: Modern, fast web framework for building APIs
- **SQLite Database**: Lightweight database with SQLAlchemy ORM
- **Pydantic Models**: Data validation and serialization
- **Jinja2 Templates**: Beautiful web interface (OWA - Outlook Web App)
- **SMTP Server**: Built-in SMTP server for receiving emails
- **ActiveSync Support**: Mobile device synchronization
- **User Authentication**: JWT-based authentication
- **Email Management**: Send, receive, read, delete emails
- **Web Interface**: Modern, responsive web UI

## Project Structure

```
365/
├── app/                    # Main application code
│   ├── routers/           # API route handlers
│   ├── templates/         # Jinja2 HTML templates
│   ├── static/           # CSS, JS, images
│   ├── database.py       # Database models and connection
│   ├── auth.py           # Authentication logic
│   ├── email_service.py  # Email business logic
│   ├── smtp_server.py    # SMTP server implementation
│   ├── smtp_client.py    # SMTP client for external delivery
│   ├── email_queue.py    # Email queue system
│   ├── email_delivery.py # Email delivery service
│   ├── mx_lookup.py      # MX record lookup
│   └── smtp_logger.py    # Comprehensive logging
├── test_scripts/         # Test scripts and utilities
├── logs/                 # SMTP and system logs
├── run.py               # Main application runner
├── run_smtp25.py        # SMTP server on port 25 (requires root)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   # For development (port 1026)
   python run.py
   
   # For production (port 25, requires root)
   sudo python run_smtp25.py
   ```

3. **Access the System**:
   - Web Interface: http://localhost:8000/owa
   - API Documentation: http://localhost:8000/docs
   - SMTP Server: localhost:1026 (dev) or localhost:25 (prod)
   - ActiveSync: http://localhost:8000/activesync

## API Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login and get access token

### Email Operations
- `GET /emails/` - Get user emails (inbox, sent, deleted)
- `POST /emails/send` - Send a new email
- `GET /emails/{id}` - Get specific email
- `PUT /emails/{id}/read` - Mark email as read
- `DELETE /emails/{id}` - Delete email
- `GET /emails/stats/summary` - Get email statistics

### OWA (Outlook Web App)
- `GET /owa/` - Dashboard
- `GET /owa/inbox` - Inbox view
- `GET /owa/compose` - Compose email
- `GET /owa/email/{id}` - View email

### ActiveSync
- `POST /activesync/sync` - Sync emails with mobile device
- `GET /activesync/ping` - Check connectivity
- `POST /activesync/provision` - Device provisioning
- `GET /activesync/folders` - Get email folders
- `GET /activesync/folders/{id}/emails` - Get folder emails

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `email`: Unique email address
- `hashed_password`: Bcrypt hashed password
- `full_name`: User's full name
- `is_active`: Account status
- `created_at`: Account creation timestamp

### Emails Table
- `id`: Primary key
- `subject`: Email subject
- `body`: Email content
- `sender_id`: Foreign key to users table
- `recipient_id`: Foreign key to users table
- `is_read`: Read status
- `is_deleted`: Soft delete flag
- `created_at`: Email creation timestamp
- `updated_at`: Last update timestamp

## Usage Examples

### 1. Register a User
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "secure_password",
    "full_name": "John Doe"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john_doe&password=secure_password"
```

### 3. Send Email
```bash
curl -X POST "http://localhost:8000/emails/send" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Hello World",
    "body": "This is a test email",
    "recipient_email": "jane@example.com"
  }'
```

### 4. Get Emails
```bash
curl -X GET "http://localhost:8000/emails/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## SMTP Configuration

The system includes a built-in SMTP server running on port 1025. You can configure email clients to use:
- **SMTP Server**: localhost
- **Port**: 1025
- **Authentication**: Not required for local testing

## ActiveSync Configuration

For mobile device synchronization, configure your email client with:
- **Server**: localhost:8000/activesync
- **Username**: Your registered username
- **Password**: Your account password
- **Protocol**: ActiveSync

## Development

### Project Structure
```
365/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database models and connection
│   ├── models.py            # Pydantic models
│   ├── auth.py              # Authentication logic
│   ├── email_service.py     # Email business logic
│   ├── smtp_server.py       # SMTP server implementation
│   └── routers/
│       ├── auth.py          # Authentication endpoints
│       ├── emails.py        # Email endpoints
│       ├── owa.py           # OWA web interface
│       └── activesync.py    # ActiveSync endpoints
├── templates/
│   └── owa/                 # Jinja2 templates
├── requirements.txt         # Python dependencies
├── run.py                  # Application entry point
└── README.md               # This file
```

### Adding New Features

1. **New API Endpoints**: Add to appropriate router in `app/routers/`
2. **Database Changes**: Update models in `app/database.py`
3. **New Templates**: Add Jinja2 templates in `templates/`
4. **Business Logic**: Add to service classes in `app/`

## Security Considerations

- Change the `SECRET_KEY` in production
- Use HTTPS in production
- Implement rate limiting
- Add input validation
- Use environment variables for sensitive data

## Testing

### Test Scripts
All test scripts are located in the `test_scripts/` directory:

```bash
# Test the entire system
python test_scripts/test_system.py

# Test SMTP server
python test_scripts/test_smtp_server.py

# Test email reception
python test_scripts/test_logging.py

# Monitor logs in real-time
python test_scripts/monitor_logs.py
```

### Database Management
```bash
# Fix database schema issues
python test_scripts/fix_database.py

# Check emails in database
python test_scripts/check_emails.py
```

### Comprehensive Logging
The system includes detailed logging for debugging:
- `logs/internal_smtp.log` - Internal SMTP server logs
- `logs/external_smtp.log` - External SMTP client logs
- `logs/email_processing.log` - Email processing logs
- `logs/smtp_connections.log` - Connection logs
- `logs/smtp_errors.log` - Error logs

## License

This project is for educational purposes. Use responsibly and in accordance with applicable laws and regulations.
