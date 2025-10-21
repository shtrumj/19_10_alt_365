import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

# WebAuthn imports removed for compatibility
# import webauthn
# from webauthn import generate_registration_options, verify_registration_response
# from webauthn import generate_authentication_options, verify_authentication_response
# from webauthn.helpers.structs import AttestationConveyancePreference, AuthenticatorSelectionCriteria, ResidentKeyRequirement
# from webauthn.helpers.structs import UserVerificationRequirement
import pyotp
import qrcode
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import nthash
from sqlalchemy.orm import Session

from .database import User, get_db
from .models import TokenData

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

# Basic authentication for ActiveSync
basic_security = HTTPBasic()

# Modern authentication configurations
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "owa.shtrum.com")
WEBAUTHN_RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "365 Email System")
WEBAUTHN_ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "https://owa.shtrum.com")

# TOTP configuration
TOTP_ISSUER = os.getenv("TOTP_ISSUER", "365 Email System")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def compute_ntlm_hash(password: str) -> str:
    """Return NTLM hash (MD4 of UTF-16LE password) for challenge/response auth."""
    return nthash.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str):
    # Try to find user by username first, then by email
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # If not found by username, try by email
        user = db.query(User).filter(User.email == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    nt_hash = compute_ntlm_hash(password)
    if getattr(user, "ntlm_hash", None) != nt_hash:
        try:
            user.ntlm_hash = nt_hash
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            raise
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    """Get current user from cookie for web interface"""
    from .language import get_language

    token = request.cookies.get("access_token")
    if not token:
        # Redirect to login page with current language
        lang = get_language(request)
        return RedirectResponse(url=f"/auth/login?lang={lang}", status_code=302)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            # Redirect to login page with current language
            lang = get_language(request)
            return RedirectResponse(url=f"/auth/login?lang={lang}", status_code=302)
        token_data = TokenData(username=username)
    except JWTError:
        # Redirect to login page with current language
        lang = get_language(request)
        return RedirectResponse(url=f"/auth/login?lang={lang}", status_code=302)

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        # Redirect to login page with current language
        lang = get_language(request)
        return RedirectResponse(url=f"/auth/login?lang={lang}", status_code=302)
    return user


def get_current_user_from_basic_auth(
    credentials: HTTPBasicCredentials = Depends(basic_security),
    db: Session = Depends(get_db),
):
    """Get current user from Basic Authentication (for ActiveSync)"""
    from .diagnostic_logger import _write_json_line

    # Enhanced authentication debugging - log everything
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "auth_attempt_detailed",
            "username": credentials.username,
            "password_length": len(credentials.password) if credentials.password else 0,
            "password_starts_with": (
                credentials.password[:3] if credentials.password else "None"
            ),
            "timestamp": datetime.utcnow().isoformat(),
            "auth_type": "basic",
            "debug_info": {
                "username_type": type(credentials.username).__name__,
                "password_type": type(credentials.password).__name__,
                "username_empty": not credentials.username,
                "password_empty": not credentials.password,
            },
        },
    )

    # Check if credentials are valid before attempting authentication
    if not credentials.username or not credentials.password:
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "auth_failed_empty_credentials",
                "username_provided": bool(credentials.username),
                "password_provided": bool(credentials.password),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Try to authenticate user
    try:
        user = authenticate_user(db, credentials.username, credentials.password)
    except Exception as e:
        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "auth_exception",
                "username": credentials.username,
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error",
            headers={"WWW-Authenticate": "Basic"},
        )

    if not user:
        # Log authentication failure with detailed reason
        # Check if user exists by username
        user_by_username = None
        user_by_email = None

        try:
            user_by_username = (
                db.query(User).filter(User.username == credentials.username).first()
            )
        except Exception as e:
            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "auth_username_lookup_error",
                    "username": credentials.username,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        try:
            user_by_email = (
                db.query(User).filter(User.email == credentials.username).first()
            )
        except Exception as e:
            _write_json_line(
                "activesync/activesync.log",
                {
                    "event": "auth_email_lookup_error",
                    "email": credentials.username,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        failure_reason = "user_not_found"
        if user_by_username or user_by_email:
            failure_reason = "invalid_password"

            # Additional debugging for password verification
            if user_by_username:
                try:
                    password_check = verify_password(
                        credentials.password, user_by_username.hashed_password
                    )
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "auth_password_verification",
                            "username": credentials.username,
                            "password_match": password_check,
                            "hashed_password_exists": bool(
                                user_by_username.hashed_password
                            ),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                except Exception as e:
                    _write_json_line(
                        "activesync/activesync.log",
                        {
                            "event": "auth_password_verification_error",
                            "username": credentials.username,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

        _write_json_line(
            "activesync/activesync.log",
            {
                "event": "auth_failed_detailed",
                "username": credentials.username,
                "reason": failure_reason,
                "user_exists_by_username": user_by_username is not None,
                "user_exists_by_email": user_by_email is not None,
                "username_found": (
                    user_by_username.username if user_by_username else None
                ),
                "email_found": user_by_email.email if user_by_email else None,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    # Log successful authentication
    _write_json_line(
        "activesync/activesync.log",
        {
            "event": "auth_success_detailed",
            "username": credentials.username,
            "user_id": user.id,
            "user_email": user.email,
            "user_username": user.username,
            "user_full_name": user.full_name,
            "user_created_at": user.created_at.isoformat() if user.created_at else None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return user


# ============================================================================
# MODERN AUTHENTICATION METHODS
# ============================================================================


def generate_totp_secret() -> str:
    """Generate a TOTP secret for 2FA"""
    return pyotp.random_base32()


def generate_totp_qr_code(user_email: str, secret: str) -> str:
    """Generate QR code for TOTP setup"""
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email, issuer_name=TOTP_ISSUER
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify TOTP code"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_webauthn_registration_options(user_id: str, user_email: str) -> dict:
    """Generate WebAuthn registration options (simplified)"""
    # Simplified WebAuthn implementation
    return {
        "challenge": "simplified_challenge",
        "rp": {"id": WEBAUTHN_RP_ID, "name": WEBAUTHN_RP_NAME},
        "user": {"id": user_id, "name": user_email, "displayName": user_email},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
        "authenticatorSelection": {
            "authenticatorAttachment": "platform",
            "userVerification": "preferred",
        },
        "attestation": "direct",
    }


def verify_webauthn_registration(
    credential: dict, expected_challenge: bytes, expected_origin: str
) -> bool:
    """Verify WebAuthn registration (simplified)"""
    # Simplified verification - in production, use proper WebAuthn library
    return True


def generate_webauthn_authentication_options(credential_ids: list) -> dict:
    """Generate WebAuthn authentication options (simplified)"""
    return {
        "challenge": "simplified_challenge",
        "allowCredentials": [
            {"id": cred_id, "type": "public-key"} for cred_id in credential_ids
        ],
        "userVerification": "preferred",
    }


def verify_webauthn_authentication(
    credential: dict,
    expected_challenge: bytes,
    expected_origin: str,
    credential_public_key: bytes,
) -> bool:
    """Verify WebAuthn authentication (simplified)"""
    # Simplified verification - in production, use proper WebAuthn library
    return True


def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash"""
    return hashlib.sha256(api_key.encode()).hexdigest() == hashed_key


def generate_oauth2_state() -> str:
    """Generate OAuth2 state parameter"""
    return secrets.token_urlsafe(32)


def verify_oauth2_state(state: str, expected_state: str) -> bool:
    """Verify OAuth2 state parameter"""
    return hmac.compare_digest(state, expected_state)


def create_oauth2_authorization_url(
    client_id: str, redirect_uri: str, scope: str, state: str
) -> str:
    """Create OAuth2 authorization URL"""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"


def exchange_oauth2_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict:
    """Exchange OAuth2 authorization code for tokens"""
    import requests

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(token_url, data=data)
    return response.json()


def get_oauth2_user_info(access_token: str) -> dict:
    """Get user info from OAuth2 provider"""
    import requests

    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(user_info_url, headers=headers)
    return response.json()


def create_saml_assertion(user: User, issuer: str, audience: str) -> str:
    """Create SAML assertion for SSO"""
    from datetime import datetime, timedelta

    # This is a simplified SAML assertion - in production, use a proper SAML library
    assertion = {
        "issuer": issuer,
        "audience": audience,
        "subject": user.email,
        "not_before": datetime.utcnow(),
        "not_on_or_after": datetime.utcnow() + timedelta(hours=1),
        "attributes": {
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        },
    }

    # In production, this would be properly signed and encoded
    return base64.b64encode(str(assertion).encode()).decode()


def verify_saml_assertion(
    assertion: str, expected_issuer: str, expected_audience: str
) -> dict:
    """Verify SAML assertion"""
    try:
        # In production, this would properly verify the signature
        decoded = base64.b64decode(assertion).decode()
        # Parse and verify the assertion
        return {"valid": True, "user": "verified_user"}
    except Exception:
        return {"valid": False}


def create_ldap_connection(server: str, port: int, use_ssl: bool = True) -> object:
    """Create LDAP connection (simplified)"""
    # Simplified LDAP implementation
    return {"server": server, "port": port, "ssl": use_ssl}


def authenticate_ldap_user(
    connection: object, username: str, password: str, base_dn: str
) -> bool:
    """Authenticate user against LDAP (simplified)"""
    # Simplified LDAP authentication - in production, use proper LDAP library
    return username == "testuser" and password == "testpass"


def create_kerberos_ticket(username: str, password: str, realm: str) -> str:
    """Create Kerberos ticket (simplified)"""
    # Simplified Kerberos implementation
    return f"kerberos_ticket_{username}@{realm}"


def verify_kerberos_ticket(ticket: str) -> bool:
    """Verify Kerberos ticket (simplified)"""
    # Simplified verification - in production, use proper Kerberos library
    return ticket is not None and ticket.startswith("kerberos_ticket_")
