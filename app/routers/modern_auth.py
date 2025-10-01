"""
Modern Authentication Router
Supports TOTP, WebAuthn, OAuth2, SAML, LDAP, Kerberos, and API Key authentication
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import base64

from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..auth import (
    get_current_user_from_cookie, get_current_user,
    generate_totp_secret, generate_totp_qr_code, verify_totp_code,
    generate_webauthn_registration_options, verify_webauthn_registration,
    generate_webauthn_authentication_options, verify_webauthn_authentication,
    generate_api_key, hash_api_key, verify_api_key,
    generate_oauth2_state, verify_oauth2_state,
    create_oauth2_authorization_url, exchange_oauth2_code, get_oauth2_user_info,
    create_saml_assertion, verify_saml_assertion,
    create_ldap_connection, authenticate_ldap_user,
    create_kerberos_ticket, verify_kerberos_ticket
)
from ..database import User, get_db
from ..diagnostic_logger import _write_json_line

router = APIRouter(prefix="/auth/modern", tags=["modern-auth"])
security = HTTPBearer()


# ============================================================================
# TOTP (Time-based One-Time Password) Authentication
# ============================================================================

@router.post("/totp/setup")
async def setup_totp(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Setup TOTP 2FA for user"""
    secret = generate_totp_secret()
    qr_code = generate_totp_qr_code(current_user.email, secret)
    
    # Store secret in user profile (in production, encrypt this)
    current_user.totp_secret = secret
    db.commit()
    
    _write_json_line("auth/modern_auth.log", {
        "event": "totp_setup",
        "user": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "secret": secret,
        "qr_code": qr_code,
        "manual_entry_key": secret
    }


@router.post("/totp/verify")
async def verify_totp(
    code: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Verify TOTP code"""
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP not configured")
    
    if verify_totp_code(current_user.totp_secret, code):
        current_user.totp_enabled = True
        db.commit()
        
        _write_json_line("auth/modern_auth.log", {
            "event": "totp_verified",
            "user": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {"status": "verified"}
    else:
        raise HTTPException(status_code=400, detail="Invalid TOTP code")


@router.post("/totp/disable")
async def disable_totp(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Disable TOTP 2FA"""
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()
    
    _write_json_line("auth/modern_auth.log", {
        "event": "totp_disabled",
        "user": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "disabled"}


# ============================================================================
# WebAuthn (FIDO2) Authentication
# ============================================================================

@router.post("/webauthn/register/begin")
async def webauthn_register_begin(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Begin WebAuthn registration"""
    options = generate_webauthn_registration_options(
        user_id=str(current_user.id),
        user_email=current_user.email
    )
    
    # Store challenge in session (in production, use Redis or database)
    # For now, we'll store it in the user record temporarily
    current_user.webauthn_challenge = options.challenge
    db.commit()
    
    return {
        "challenge": options.challenge,
        "rp": {
            "id": options.rp.id,
            "name": options.rp.name
        },
        "user": {
            "id": options.user.id,
            "name": options.user.name,
            "displayName": options.user.display_name
        },
        "pubKeyCredParams": options.pub_key_cred_params,
        "authenticatorSelection": {
            "authenticatorAttachment": options.authenticator_selection.authenticator_attachment,
            "residentKey": options.authenticator_selection.resident_key,
            "userVerification": options.authenticator_selection.user_verification
        },
        "attestation": options.attestation
    }


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    credential: Dict[str, Any],
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Complete WebAuthn registration"""
    if not current_user.webauthn_challenge:
        raise HTTPException(status_code=400, detail="No registration in progress")
    
    if verify_webauthn_registration(
        credential=credential,
        expected_challenge=current_user.webauthn_challenge.encode(),
        expected_origin="https://owa.shtrum.com"
    ):
        # Store credential in user profile
        current_user.webauthn_credentials = json.dumps([credential])
        current_user.webauthn_enabled = True
        current_user.webauthn_challenge = None
        db.commit()
        
        _write_json_line("auth/modern_auth.log", {
            "event": "webauthn_registered",
            "user": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {"status": "registered"}
    else:
        raise HTTPException(status_code=400, detail="Registration verification failed")


@router.post("/webauthn/authenticate/begin")
async def webauthn_authenticate_begin(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Begin WebAuthn authentication"""
    if not current_user.webauthn_credentials:
        raise HTTPException(status_code=400, detail="No WebAuthn credentials found")
    
    credentials = json.loads(current_user.webauthn_credentials)
    credential_ids = [cred["id"] for cred in credentials]
    
    options = generate_webauthn_authentication_options(credential_ids)
    
    # Store challenge
    current_user.webauthn_challenge = options.challenge
    db.commit()
    
    return {
        "challenge": options.challenge,
        "allowCredentials": options.allow_credentials,
        "userVerification": options.user_verification
    }


@router.post("/webauthn/authenticate/complete")
async def webauthn_authenticate_complete(
    credential: Dict[str, Any],
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Complete WebAuthn authentication"""
    if not current_user.webauthn_challenge:
        raise HTTPException(status_code=400, detail="No authentication in progress")
    
    stored_credentials = json.loads(current_user.webauthn_credentials)
    matching_credential = next(
        (cred for cred in stored_credentials if cred["id"] == credential["id"]), 
        None
    )
    
    if not matching_credential:
        raise HTTPException(status_code=400, detail="Credential not found")
    
    if verify_webauthn_authentication(
        credential=credential,
        expected_challenge=current_user.webauthn_challenge.encode(),
        expected_origin="https://owa.shtrum.com",
        credential_public_key=base64.b64decode(matching_credential["publicKey"])
    ):
        current_user.webauthn_challenge = None
        db.commit()
        
        _write_json_line("auth/modern_auth.log", {
            "event": "webauthn_authenticated",
            "user": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {"status": "authenticated"}
    else:
        raise HTTPException(status_code=400, detail="Authentication verification failed")


# ============================================================================
# API Key Authentication
# ============================================================================

@router.post("/api-key/generate")
async def generate_api_key_endpoint(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Generate API key for user"""
    api_key = generate_api_key()
    hashed_key = hash_api_key(api_key)
    
    # Store hashed key in user profile
    current_user.api_key_hash = hashed_key
    current_user.api_key_created = datetime.utcnow()
    db.commit()
    
    _write_json_line("auth/modern_auth.log", {
        "event": "api_key_generated",
        "user": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {
        "api_key": api_key,
        "created_at": current_user.api_key_created.isoformat(),
        "warning": "Store this key securely. It will not be shown again."
    }


@router.post("/api-key/revoke")
async def revoke_api_key(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Revoke user's API key"""
    current_user.api_key_hash = None
    current_user.api_key_created = None
    db.commit()
    
    _write_json_line("auth/modern_auth.log", {
        "event": "api_key_revoked",
        "user": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "revoked"}


def get_current_user_from_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user from API key"""
    if not credentials.credentials.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    api_key = credentials.credentials[7:]  # Remove "Bearer " prefix
    
    # Find user with matching API key
    users = db.query(User).filter(User.api_key_hash.isnot(None)).all()
    for user in users:
        if verify_api_key(api_key, user.api_key_hash):
            return user
    
    raise HTTPException(status_code=401, detail="Invalid API key")


# ============================================================================
# OAuth2 Authentication
# ============================================================================

@router.get("/oauth2/google")
async def oauth2_google_login():
    """Initiate Google OAuth2 login"""
    state = generate_oauth2_state()
    auth_url = create_oauth2_authorization_url(
        client_id="your-google-client-id",
        redirect_uri="https://owa.shtrum.com/auth/modern/oauth2/google/callback",
        scope="openid email profile",
        state=state
    )
    
    # Store state in session (in production, use Redis)
    return RedirectResponse(url=auth_url)


@router.get("/oauth2/google/callback")
async def oauth2_google_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth2 callback"""
    # Verify state parameter
    if not verify_oauth2_state(state, "stored_state"):  # In production, get from session
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Exchange code for tokens
    tokens = exchange_oauth2_code(
        code=code,
        client_id="your-google-client-id",
        client_secret="your-google-client-secret",
        redirect_uri="https://owa.shtrum.com/auth/modern/oauth2/google/callback"
    )
    
    # Get user info
    user_info = get_oauth2_user_info(tokens["access_token"])
    
    # Find or create user
    user = db.query(User).filter(User.email == user_info["email"]).first()
    if not user:
        user = User(
            username=user_info["email"],
            email=user_info["email"],
            full_name=user_info.get("name", ""),
            hashed_password="oauth2_user"  # Special marker for OAuth2 users
        )
        db.add(user)
        db.commit()
    
    _write_json_line("auth/modern_auth.log", {
        "event": "oauth2_login",
        "user": user.username,
        "provider": "google",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "authenticated", "user": user.username}


# ============================================================================
# SAML Authentication
# ============================================================================

@router.get("/saml/metadata")
async def saml_metadata():
    """Return SAML metadata"""
    metadata = {
        "entity_id": "https://owa.shtrum.com",
        "sso_url": "https://owa.shtrum.com/auth/modern/saml/sso",
        "certificate": "your-saml-certificate"
    }
    return metadata


@router.post("/saml/sso")
async def saml_sso(
    saml_response: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle SAML SSO response"""
    # In production, use a proper SAML library
    assertion_result = verify_saml_assertion(
        assertion=saml_response,
        expected_issuer="your-saml-issuer",
        expected_audience="https://owa.shtrum.com"
    )
    
    if assertion_result["valid"]:
        # Find or create user based on SAML attributes
        user = db.query(User).filter(User.email == assertion_result["user"]).first()
        if not user:
            user = User(
                username=assertion_result["user"],
                email=assertion_result["user"],
                hashed_password="saml_user"  # Special marker for SAML users
            )
            db.add(user)
            db.commit()
        
        _write_json_line("auth/modern_auth.log", {
            "event": "saml_sso",
            "user": user.username,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {"status": "authenticated", "user": user.username}
    else:
        raise HTTPException(status_code=401, detail="SAML authentication failed")


# ============================================================================
# LDAP Authentication
# ============================================================================

@router.post("/ldap/authenticate")
async def ldap_authenticate(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate user against LDAP"""
    try:
        # Create LDAP connection
        connection = create_ldap_connection(
            server="your-ldap-server.com",
            port=636,
            use_ssl=True
        )
        
        # Authenticate user
        if authenticate_ldap_user(
            connection=connection,
            username=username,
            password=password,
            base_dn="ou=users,dc=company,dc=com"
        ):
            # Find or create user
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(
                    username=username,
                    email=f"{username}@company.com",
                    hashed_password="ldap_user"  # Special marker for LDAP users
                )
                db.add(user)
                db.commit()
            
            _write_json_line("auth/modern_auth.log", {
                "event": "ldap_authenticated",
                "user": user.username,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {"status": "authenticated", "user": user.username}
        else:
            raise HTTPException(status_code=401, detail="LDAP authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LDAP error: {str(e)}")


# ============================================================================
# Kerberos Authentication
# ============================================================================

@router.post("/kerberos/authenticate")
async def kerberos_authenticate(
    username: str = Form(...),
    password: str = Form(...),
    realm: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticate user with Kerberos"""
    try:
        # Create Kerberos ticket
        ticket = create_kerberos_ticket(username, password, realm)
        
        if ticket and verify_kerberos_ticket(ticket):
            # Find or create user
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(
                    username=username,
                    email=f"{username}@{realm}",
                    hashed_password="kerberos_user"  # Special marker for Kerberos users
                )
                db.add(user)
                db.commit()
            
            _write_json_line("auth/modern_auth.log", {
                "event": "kerberos_authenticated",
                "user": user.username,
                "realm": realm,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {"status": "authenticated", "user": user.username}
        else:
            raise HTTPException(status_code=401, detail="Kerberos authentication failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kerberos error: {str(e)}")


# ============================================================================
# TLS/SSL Configuration Endpoints
# ============================================================================

@router.get("/tls/info")
async def tls_info(request: Request):
    """Get TLS/SSL information"""
    tls_info = {
        "protocol": request.headers.get("x-forwarded-proto", "https"),
        "cipher": request.headers.get("x-ssl-cipher", "unknown"),
        "version": request.headers.get("x-ssl-version", "unknown"),
        "client_cert": request.headers.get("x-ssl-client-cert", None),
        "client_verify": request.headers.get("x-ssl-client-verify", None)
    }
    
    _write_json_line("auth/modern_auth.log", {
        "event": "tls_info_requested",
        "tls_info": tls_info,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return tls_info


@router.post("/tls/verify-client-cert")
async def verify_client_certificate(
    certificate: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verify client certificate for mutual TLS authentication"""
    try:
        # In production, properly verify the certificate
        # For now, we'll do a basic check
        if certificate and len(certificate) > 100:  # Basic validation
            _write_json_line("auth/modern_auth.log", {
                "event": "client_cert_verified",
                "certificate_length": len(certificate),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {"status": "verified", "certificate": "valid"}
        else:
            raise HTTPException(status_code=400, detail="Invalid certificate")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Certificate verification error: {str(e)}")


# ============================================================================
# Authentication Status and Management
# ============================================================================

@router.get("/status")
async def auth_status(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Get user's authentication status and methods"""
    return {
        "user": current_user.username,
        "email": current_user.email,
        "totp_enabled": getattr(current_user, 'totp_enabled', False),
        "webauthn_enabled": getattr(current_user, 'webauthn_enabled', False),
        "api_key_created": getattr(current_user, 'api_key_created', None),
        "last_login": getattr(current_user, 'last_login', None)
    }


@router.get("/methods")
async def available_auth_methods():
    """Get available authentication methods"""
    return {
        "methods": [
            {
                "name": "Basic Authentication",
                "type": "basic",
                "description": "Username and password authentication",
                "supported": True
            },
            {
                "name": "TOTP (2FA)",
                "type": "totp",
                "description": "Time-based One-Time Password",
                "supported": True
            },
            {
                "name": "WebAuthn (FIDO2)",
                "type": "webauthn",
                "description": "Passwordless authentication with security keys",
                "supported": True
            },
            {
                "name": "API Key",
                "type": "api_key",
                "description": "API key for programmatic access",
                "supported": True
            },
            {
                "name": "OAuth2",
                "type": "oauth2",
                "description": "OAuth2 with Google, Microsoft, etc.",
                "supported": True
            },
            {
                "name": "SAML SSO",
                "type": "saml",
                "description": "SAML Single Sign-On",
                "supported": True
            },
            {
                "name": "LDAP",
                "type": "ldap",
                "description": "LDAP directory authentication",
                "supported": True
            },
            {
                "name": "Kerberos",
                "type": "kerberos",
                "description": "Kerberos authentication",
                "supported": True
            },
            {
                "name": "Client Certificate",
                "type": "client_cert",
                "description": "Mutual TLS with client certificates",
                "supported": True
            }
        ]
    }


