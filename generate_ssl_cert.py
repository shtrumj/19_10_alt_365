#!/usr/bin/env python3
"""
Generate self-signed SSL certificates for SMTP server
"""
import os
import ssl
import socket
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

def generate_ssl_certificates():
    """Generate self-signed SSL certificates for SMTP server"""
    try:
        # Create SSL directory
        ssl_dir = os.path.join(os.path.dirname(__file__), 'ssl')
        os.makedirs(ssl_dir, exist_ok=True)
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IL"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Israel"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Tel Aviv"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "365 Email System"),
            x509.NameAttribute(NameOID.COMMON_NAME, "smtp.shtrum.com"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("smtp.shtrum.com"),
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write private key
        key_file = os.path.join(ssl_dir, 'smtp.key')
        with open(key_file, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Write certificate
        cert_file = os.path.join(ssl_dir, 'smtp.crt')
        with open(cert_file, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"✅ SSL certificates generated successfully:")
        print(f"   Private key: {key_file}")
        print(f"   Certificate: {cert_file}")
        
        # Set permissions
        os.chmod(key_file, 0o600)
        os.chmod(cert_file, 0o644)
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating SSL certificates: {e}")
        return False

if __name__ == "__main__":
    generate_ssl_certificates()
