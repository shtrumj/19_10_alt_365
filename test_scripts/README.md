# Test Scripts Directory

This directory contains all test scripts and utility tools for the 365 Email System.

## Test Scripts

### Core System Tests
- **`test_system.py`** - Comprehensive system test that tests the entire email system
- **`test_email_service.py`** - Tests the email service functionality
- **`test_mx_lookup.py`** - Tests MX record lookup functionality

### SMTP Server Tests
- **`test_smtp25.py`** - Tests SMTP server on port 25
- **`test_smtp_connection.py`** - Tests SMTP server connection
- **`test_smtp_handler.py`** - Tests SMTP handler directly
- **`test_smtp_receive.py`** - Tests email reception via SMTP
- **`test_smtp_server.py`** - Tests SMTP server with handler
- **`test_telnet_smtp.py`** - Tests SMTP server with telnet-like connection

### Email Testing
- **`test_new_email.py`** - Tests sending new emails and checking database
- **`test_logging.py`** - Tests SMTP logging system

## Utility Scripts

### Database Management
- **`fix_database.py`** - Fixes database schema issues
- **`migrate_database.py`** - Database migration script
- **`check_emails.py`** - Checks emails in database

### Debugging Tools
- **`debug_smtp.py`** - Debug SMTP server configuration
- **`monitor_logs.py`** - Monitor SMTP logs in real-time

## Usage

### Running Tests
```bash
# Test the entire system
python test_scripts/test_system.py

# Test SMTP server
python test_scripts/test_smtp_server.py

# Test email reception
python test_scripts/test_logging.py
```

### Database Management
```bash
# Fix database schema
python test_scripts/fix_database.py

# Check emails in database
python test_scripts/check_emails.py
```

### Monitoring
```bash
# Monitor logs in real-time
python test_scripts/monitor_logs.py
```

## Notes

- All scripts are designed to be run from the project root directory
- Test scripts may require the SMTP server to be running
- Some scripts require root privileges for port 25 testing
- Logs are written to the `logs/` directory in the project root
