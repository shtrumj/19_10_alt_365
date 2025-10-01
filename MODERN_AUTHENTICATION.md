# Modern Authentication System

This document describes the comprehensive modern authentication system implemented in the 365 Email System, supporting multiple authentication methods and TLS/SSL protocols.

## 🔐 Supported Authentication Methods

### 1. Basic Authentication
- **Type**: Username/Password
- **Security**: Standard HTTP Basic Auth
- **Use Case**: ActiveSync, API access
- **Endpoint**: `/auth/login`

### 2. TOTP (Time-based One-Time Password)
- **Type**: 2FA with authenticator apps
- **Security**: High (time-based codes)
- **Use Case**: Enhanced security for user accounts
- **Endpoints**: 
  - `/auth/modern/totp/setup` - Setup TOTP
  - `/auth/modern/totp/verify` - Verify TOTP code
  - `/auth/modern/totp/disable` - Disable TOTP

### 3. WebAuthn (FIDO2)
- **Type**: Passwordless authentication
- **Security**: Very High (hardware security keys)
- **Use Case**: Passwordless login with security keys
- **Endpoints**:
  - `/auth/modern/webauthn/register/begin` - Start registration
  - `/auth/modern/webauthn/register/complete` - Complete registration
  - `/auth/modern/webauthn/authenticate/begin` - Start authentication
  - `/auth/modern/webauthn/authenticate/complete` - Complete authentication

### 4. API Key Authentication
- **Type**: Programmatic access
- **Security**: High (long-lived tokens)
- **Use Case**: API access, automation
- **Endpoints**:
  - `/auth/modern/api-key/generate` - Generate API key
  - `/auth/modern/api-key/revoke` - Revoke API key

### 5. OAuth2
- **Type**: Third-party authentication
- **Security**: High (OAuth2 flow)
- **Use Case**: Google, Microsoft, GitHub login
- **Endpoints**:
  - `/auth/modern/oauth2/google` - Google OAuth2
  - `/auth/modern/oauth2/google/callback` - OAuth2 callback

### 6. SAML SSO
- **Type**: Enterprise SSO
- **Security**: Very High (enterprise-grade)
- **Use Case**: Corporate authentication
- **Endpoints**:
  - `/auth/modern/saml/metadata` - SAML metadata
  - `/auth/modern/saml/sso` - SAML SSO

### 7. LDAP
- **Type**: Directory authentication
- **Security**: High (directory integration)
- **Use Case**: Corporate directory integration
- **Endpoints**:
  - `/auth/modern/ldap/authenticate` - LDAP authentication

### 8. Kerberos
- **Type**: Network authentication
- **Security**: Very High (ticket-based)
- **Use Case**: Windows domain authentication
- **Endpoints**:
  - `/auth/modern/kerberos/authenticate` - Kerberos authentication

### 9. Client Certificate (Mutual TLS)
- **Type**: Certificate-based authentication
- **Security**: Very High (PKI-based)
- **Use Case**: High-security environments
- **Endpoints**:
  - `/auth/modern/tls/verify-client-cert` - Certificate verification

## 🔒 TLS/SSL Configuration

### Supported Protocols
- **TLS 1.2**: Full support with modern cipher suites
- **TLS 1.3**: Latest protocol with enhanced security
- **Legacy Support**: Disabled for security

### Cipher Suites
```
ECDHE-ECDSA-AES128-GCM-SHA256
ECDHE-RSA-AES128-GCM-SHA256
ECDHE-ECDSA-AES256-GCM-SHA384
ECDHE-RSA-AES256-GCM-SHA384
ECDHE-ECDSA-CHACHA20-POLY1305
ECDHE-RSA-CHACHA20-POLY1305
DHE-RSA-AES128-GCM-SHA256
DHE-RSA-AES256-GCM-SHA384
```

### Security Features
- **HSTS**: HTTP Strict Transport Security
- **OCSP Stapling**: Certificate status checking
- **Perfect Forward Secrecy**: Ephemeral key exchange
- **Certificate Transparency**: CT logs support
- **Security Headers**: Comprehensive protection

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Database Migration
```bash
python migrate_modern_auth.py
```

### 3. Configure Environment Variables
```bash
# WebAuthn Configuration
export WEBAUTHN_RP_ID="owa.shtrum.com"
export WEBAUTHN_RP_NAME="365 Email System"
export WEBAUTHN_ORIGIN="https://owa.shtrum.com"

# TOTP Configuration
export TOTP_ISSUER="365 Email System"

# OAuth2 Configuration
export GOOGLE_CLIENT_ID="your-google-client-id"
export GOOGLE_CLIENT_SECRET="your-google-client-secret"

# LDAP Configuration
export LDAP_SERVER="your-ldap-server.com"
export LDAP_PORT="636"
export LDAP_BASE_DN="ou=users,dc=company,dc=com"

# SAML Configuration
export SAML_ISSUER="your-saml-issuer"
export SAML_AUDIENCE="https://owa.shtrum.com"
```

### 4. Start the Application
```bash
docker-compose up -d
```

## 📱 Client Integration

### ActiveSync Clients
Modern authentication is fully compatible with ActiveSync clients:
- **Outlook**: Supports all authentication methods
- **iPhone**: Native support for modern auth
- **Android**: Full compatibility
- **Third-party**: Standard protocols

### Web Clients
- **OWA**: Full modern authentication support
- **Mobile**: Responsive design
- **API**: RESTful endpoints

## 🔧 Configuration Examples

### TOTP Setup
```python
# Generate TOTP secret
secret = generate_totp_secret()

# Generate QR code
qr_code = generate_totp_qr_code(user_email, secret)

# Verify TOTP code
is_valid = verify_totp_code(secret, user_code)
```

### WebAuthn Registration
```python
# Begin registration
options = generate_webauthn_registration_options(user_id, user_email)

# Complete registration
is_valid = verify_webauthn_registration(credential, challenge, origin)
```

### API Key Authentication
```python
# Generate API key
api_key = generate_api_key()

# Hash for storage
hashed_key = hash_api_key(api_key)

# Verify API key
is_valid = verify_api_key(api_key, hashed_key)
```

## 🧪 Testing

### Run Authentication Tests
```bash
python test_scripts/test_modern_auth.py
```

### Test Specific Methods
```bash
# Test TOTP
python test_scripts/test_modern_auth.py --test totp

# Test WebAuthn
python test_scripts/test_modern_auth.py --test webauthn

# Test OAuth2
python test_scripts/test_modern_auth.py --test oauth2
```

## 📊 Monitoring and Logging

### Authentication Logs
- **Location**: `logs/auth/modern_auth.log`
- **Format**: JSON structured logging
- **Events**: All authentication attempts and results

### Security Monitoring
- **Rate Limiting**: Automatic protection
- **Failed Attempts**: Tracking and alerting
- **Suspicious Activity**: Detection and response

## 🔐 Security Best Practices

### 1. Password Policies
- Minimum 12 characters
- Mixed case, numbers, symbols
- Regular rotation
- No common patterns

### 2. Multi-Factor Authentication
- Enable TOTP for all users
- Encourage WebAuthn adoption
- Backup codes for recovery

### 3. API Security
- Rotate API keys regularly
- Use least privilege principle
- Monitor API usage

### 4. Certificate Management
- Regular certificate renewal
- Strong key sizes (2048+ bits)
- Proper certificate chains

## 🚨 Troubleshooting

### Common Issues

#### TOTP Not Working
- Check time synchronization
- Verify secret generation
- Ensure proper QR code scanning

#### WebAuthn Registration Fails
- Check browser compatibility
- Verify HTTPS connection
- Ensure proper origin configuration

#### LDAP Authentication Issues
- Verify server connectivity
- Check DN format
- Ensure proper SSL/TLS

#### Certificate Problems
- Check certificate validity
- Verify certificate chain
- Ensure proper key usage

### Debug Commands
```bash
# Check authentication status
curl -X GET https://owa.shtrum.com/auth/modern/status

# Test TLS configuration
curl -X GET https://owa.shtrum.com/auth/modern/tls/info

# Verify authentication methods
curl -X GET https://owa.shtrum.com/auth/modern/methods
```

## 📚 API Reference

### Authentication Endpoints
- `GET /auth/modern/methods` - Available methods
- `GET /auth/modern/status` - Authentication status
- `GET /auth/modern/tls/info` - TLS information

### TOTP Endpoints
- `POST /auth/modern/totp/setup` - Setup TOTP
- `POST /auth/modern/totp/verify` - Verify TOTP
- `POST /auth/modern/totp/disable` - Disable TOTP

### WebAuthn Endpoints
- `POST /auth/modern/webauthn/register/begin` - Start registration
- `POST /auth/modern/webauthn/register/complete` - Complete registration
- `POST /auth/modern/webauthn/authenticate/begin` - Start authentication
- `POST /auth/modern/webauthn/authenticate/complete` - Complete authentication

### API Key Endpoints
- `POST /auth/modern/api-key/generate` - Generate API key
- `POST /auth/modern/api-key/revoke` - Revoke API key

## 🔄 Migration Guide

### From Basic Auth Only
1. Run database migration
2. Configure modern auth settings
3. Enable TOTP for users
4. Test authentication methods

### From Legacy Systems
1. Export user data
2. Import to new system
3. Configure authentication methods
4. Test all integrations

## 📞 Support

### Documentation
- **API Docs**: `/docs` (Swagger UI)
- **ReDoc**: `/redoc` (Alternative docs)
- **OpenAPI**: `/openapi.json` (Schema)

### Community
- **GitHub**: Issues and discussions
- **Discord**: Real-time support
- **Email**: Support team contact

## 🎯 Roadmap

### Planned Features
- **Biometric Authentication**: Fingerprint, face recognition
- **Hardware Security Modules**: HSM integration
- **Advanced Threat Protection**: AI-powered security
- **Zero Trust Architecture**: Complete security model

### Upcoming Integrations
- **Microsoft Azure AD**: Native integration
- **Google Workspace**: Seamless SSO
- **Okta**: Enterprise identity
- **Auth0**: Universal authentication

---

**Note**: This modern authentication system provides enterprise-grade security while maintaining ease of use and compatibility with existing clients. All authentication methods are fully tested and production-ready.


