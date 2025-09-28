# Test Scripts Directory

This directory contains all test scripts for the 365 Email System project.

## 📁 Script Categories

### 🔌 WebSocket Tests
- `test_websocket.py` - Basic WebSocket functionality test
- `test_websocket_direct.py` - Direct WebSocket router testing
- `test_websocket_isolated.py` - Isolated WebSocket server test
- `test_minimal_websocket.py` - Minimal WebSocket implementation test

### 📧 Email System Tests
- `test_email_parsing.py` - Email content parsing tests
- `test_email_service.py` - Email service functionality tests
- `test_simple_email.py` - Simple email creation tests
- `test_new_email.py` - New email notification tests

### 🌐 SMTP Server Tests
- `test_smtp25.py` - SMTP server on port 25 tests
- `test_smtp_connection.py` - SMTP connection tests
- `test_smtp_handler.py` - SMTP handler tests
- `test_smtp_receive.py` - SMTP email reception tests
- `test_smtp_send.py` - SMTP email sending tests
- `test_smtp_server.py` - SMTP server functionality tests
- `test_smtp_simple.py` - Simple SMTP tests
- `test_smtpd_simple.py` - Simple SMTPD tests
- `test_tls_smtp.py` - TLS/SSL SMTP tests

### 🔐 Authentication Tests
- `test_web_login.py` - Web login functionality tests
- `test_login_debug.py` - Login debugging tests
- `test_login_final.py` - Final login tests
- `test_create_user.py` - User creation tests

### 🌍 Network Tests
- `test_mx_lookup.py` - MX record lookup tests
- `test_telnet_smtp.py` - Telnet SMTP connection tests
- `test_system_access.py` - System access tests

### 🐛 Debug Tests
- `test_debug_parsing.py` - Email parsing debug tests
- `test_template_parsing.py` - Template parsing tests
- `test_logging.py` - Logging system tests
- `debug_smtp.py` - SMTP debugging script

### 🗄️ Database Tests
- `test_database_check.py` - Database connectivity tests
- `fix_database.py` - Database repair script
- `migrate_database.py` - Database migration script

### 🔧 System Tests
- `test_system.py` - Overall system tests
- `test_live_system.py` - Live system functionality tests
- `test_web_emails.py` - Web email interface tests
- `check_emails.py` - Email checking utility
- `monitor_logs.py` - Log monitoring utility

## 🚀 Usage

### Running Individual Tests
```bash
# WebSocket tests
python test_scripts/test_websocket.py
python test_scripts/test_websocket_isolated.py

# SMTP tests
python test_scripts/test_smtp25.py
python test_scripts/test_smtp_connection.py

# Email tests
python test_scripts/test_email_parsing.py
python test_scripts/test_simple_email.py
```

### Running Tests in Docker
```bash
# Copy test script to container
docker cp test_scripts/test_websocket.py 365-email-system:/app/

# Run test in container
docker exec 365-email-system python test_websocket.py
```

### Debugging WebSocket Issues
```bash
# Test isolated WebSocket server
python test_scripts/test_websocket_isolated.py

# Test minimal WebSocket implementation
python test_scripts/test_minimal_websocket.py

# Test direct WebSocket router
python test_scripts/test_websocket_direct.py
```

## 📊 Test Results

### ✅ Working Tests
- **WebSocket Isolated Server**: ✅ Working (port 8003)
- **WebSocket Minimal Server**: ✅ Working (port 8002)
- **Email Parsing**: ✅ Working
- **SMTP Server**: ✅ Working
- **Database Operations**: ✅ Working

### ❌ Known Issues
- **Main App WebSocket**: ❌ 403 Forbidden (authentication issue)
- **WebSocket Manager Integration**: ❌ Connection conflicts

## 🔍 Debugging

### WebSocket Connection Issues
1. Check browser console for detailed error logs
2. Verify hostname configuration (`window.hostname`)
3. Test with isolated WebSocket server
4. Check Nginx WebSocket proxy configuration

### SMTP Server Issues
1. Check port 25 binding permissions
2. Verify SSL certificate generation
3. Test with telnet connection
4. Check firewall settings

### Email Parsing Issues
1. Check email content format
2. Verify parser implementation
3. Test with sample email data
4. Check template rendering

## 📝 Notes

- All test scripts are designed to be run independently
- Some tests require Docker container access
- WebSocket tests may need browser environment
- SMTP tests require proper network configuration
- Database tests require SQLite database setup

## 🛠️ Maintenance

- Keep test scripts updated with main application changes
- Add new tests for new features
- Remove obsolete tests
- Update documentation as needed