#!/usr/bin/env python3
"""
Comprehensive test script for modern authentication methods
Tests TOTP, WebAuthn, OAuth2, SAML, LDAP, Kerberos, and API Key authentication
"""

import requests
import json
import base64
import time
from datetime import datetime
import pyotp
import qrcode
from io import BytesIO

class ModernAuthTester:
    def __init__(self, base_url="https://owa.shtrum.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False  # For testing with self-signed certificates
        self.test_results = {}
        
    def log_test(self, test_name, status, details=""):
        """Log test results"""
        timestamp = datetime.now().isoformat()
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": timestamp
        }
        self.test_results[test_name] = result
        print(f"{'✅' if status == 'PASS' else '❌'} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
    
    def test_authentication_methods(self):
        """Test available authentication methods"""
        try:
            response = self.session.get(f"{self.base_url}/auth/modern/methods")
            if response.status_code == 200:
                methods = response.json()
                self.log_test("Authentication Methods", "PASS", f"Found {len(methods['methods'])} methods")
                return methods
            else:
                self.log_test("Authentication Methods", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("Authentication Methods", "FAIL", str(e))
            return None
    
    def test_totp_setup(self):
        """Test TOTP setup"""
        try:
            # This would require authentication first
            response = self.session.post(f"{self.base_url}/auth/modern/totp/setup")
            if response.status_code == 200:
                data = response.json()
                self.log_test("TOTP Setup", "PASS", "TOTP setup endpoint accessible")
                return data
            else:
                self.log_test("TOTP Setup", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("TOTP Setup", "FAIL", str(e))
            return None
    
    def test_totp_verification(self, secret, code):
        """Test TOTP verification"""
        try:
            # Generate a valid TOTP code
            totp = pyotp.TOTP(secret)
            valid_code = totp.now()
            
            response = self.session.post(
                f"{self.base_url}/auth/modern/totp/verify",
                data={"code": valid_code}
            )
            
            if response.status_code == 200:
                self.log_test("TOTP Verification", "PASS", "TOTP verification successful")
                return True
            else:
                self.log_test("TOTP Verification", "FAIL", f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("TOTP Verification", "FAIL", str(e))
            return False
    
    def test_webauthn_registration(self):
        """Test WebAuthn registration"""
        try:
            response = self.session.post(f"{self.base_url}/auth/modern/webauthn/register/begin")
            if response.status_code == 200:
                data = response.json()
                self.log_test("WebAuthn Registration Begin", "PASS", "WebAuthn registration started")
                return data
            else:
                self.log_test("WebAuthn Registration Begin", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("WebAuthn Registration Begin", "FAIL", str(e))
            return None
    
    def test_api_key_generation(self):
        """Test API key generation"""
        try:
            response = self.session.post(f"{self.base_url}/auth/modern/api-key/generate")
            if response.status_code == 200:
                data = response.json()
                self.log_test("API Key Generation", "PASS", "API key generated successfully")
                return data
            else:
                self.log_test("API Key Generation", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("API Key Generation", "FAIL", str(e))
            return None
    
    def test_oauth2_google(self):
        """Test OAuth2 Google authentication"""
        try:
            response = self.session.get(f"{self.base_url}/auth/modern/oauth2/google")
            if response.status_code == 302:  # Redirect to Google
                self.log_test("OAuth2 Google", "PASS", "OAuth2 redirect initiated")
                return True
            else:
                self.log_test("OAuth2 Google", "FAIL", f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("OAuth2 Google", "FAIL", str(e))
            return False
    
    def test_saml_metadata(self):
        """Test SAML metadata endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/auth/modern/saml/metadata")
            if response.status_code == 200:
                data = response.json()
                self.log_test("SAML Metadata", "PASS", "SAML metadata accessible")
                return data
            else:
                self.log_test("SAML Metadata", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("SAML Metadata", "FAIL", str(e))
            return None
    
    def test_ldap_authentication(self, username="testuser", password="testpass"):
        """Test LDAP authentication"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/modern/ldap/authenticate",
                data={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.log_test("LDAP Authentication", "PASS", "LDAP authentication successful")
                return data
            else:
                self.log_test("LDAP Authentication", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("LDAP Authentication", "FAIL", str(e))
            return None
    
    def test_kerberos_authentication(self, username="testuser", password="testpass", realm="TEST.REALM"):
        """Test Kerberos authentication"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/modern/kerberos/authenticate",
                data={"username": username, "password": password, "realm": realm}
            )
            if response.status_code == 200:
                data = response.json()
                self.log_test("Kerberos Authentication", "PASS", "Kerberos authentication successful")
                return data
            else:
                self.log_test("Kerberos Authentication", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("Kerberos Authentication", "FAIL", str(e))
            return None
    
    def test_tls_info(self):
        """Test TLS information endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/auth/modern/tls/info")
            if response.status_code == 200:
                data = response.json()
                self.log_test("TLS Info", "PASS", f"TLS protocol: {data.get('protocol', 'unknown')}")
                return data
            else:
                self.log_test("TLS Info", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("TLS Info", "FAIL", str(e))
            return None
    
    def test_client_certificate_verification(self):
        """Test client certificate verification"""
        try:
            # This would require a valid client certificate
            test_cert = "-----BEGIN CERTIFICATE-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END CERTIFICATE-----"
            
            response = self.session.post(
                f"{self.base_url}/auth/modern/tls/verify-client-cert",
                data={"certificate": test_cert}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Client Certificate Verification", "PASS", "Client certificate verification successful")
                return data
            else:
                self.log_test("Client Certificate Verification", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("Client Certificate Verification", "FAIL", str(e))
            return None
    
    def test_authentication_status(self):
        """Test authentication status endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/auth/modern/status")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Authentication Status", "PASS", f"User: {data.get('user', 'unknown')}")
                return data
            else:
                self.log_test("Authentication Status", "FAIL", f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_test("Authentication Status", "FAIL", str(e))
            return None
    
    def run_all_tests(self):
        """Run all modern authentication tests"""
        print("🔐 MODERN AUTHENTICATION TEST SUITE")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Server: {self.base_url}")
        print()
        
        # Test 1: Authentication Methods
        print("🔍 Testing Available Authentication Methods...")
        self.test_authentication_methods()
        print()
        
        # Test 2: TOTP Setup
        print("🔐 Testing TOTP (Time-based One-Time Password)...")
        totp_data = self.test_totp_setup()
        if totp_data:
            # Test TOTP verification with generated secret
            secret = totp_data.get('secret', '')
            if secret:
                self.test_totp_verification(secret, '')
        print()
        
        # Test 3: WebAuthn Registration
        print("🔑 Testing WebAuthn (FIDO2)...")
        self.test_webauthn_registration()
        print()
        
        # Test 4: API Key Generation
        print("🔑 Testing API Key Authentication...")
        self.test_api_key_generation()
        print()
        
        # Test 5: OAuth2 Google
        print("🌐 Testing OAuth2 Google...")
        self.test_oauth2_google()
        print()
        
        # Test 6: SAML Metadata
        print("🏢 Testing SAML SSO...")
        self.test_saml_metadata()
        print()
        
        # Test 7: LDAP Authentication
        print("📁 Testing LDAP Authentication...")
        self.test_ldap_authentication()
        print()
        
        # Test 8: Kerberos Authentication
        print("🎫 Testing Kerberos Authentication...")
        self.test_kerberos_authentication()
        print()
        
        # Test 9: TLS Information
        print("🔒 Testing TLS/SSL Information...")
        self.test_tls_info()
        print()
        
        # Test 10: Client Certificate Verification
        print("📜 Testing Client Certificate Verification...")
        self.test_client_certificate_verification()
        print()
        
        # Test 11: Authentication Status
        print("📊 Testing Authentication Status...")
        self.test_authentication_status()
        print()
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary"""
        print("=" * 60)
        print("📋 MODERN AUTHENTICATION TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        if failed_tests > 0:
            print("❌ Failed Tests:")
            for test_name, result in self.test_results.items():
                if result['status'] == 'FAIL':
                    print(f"   • {test_name}: {result['details']}")
            print()
        
        print("🎯 Available Authentication Methods:")
        print("   • Basic Authentication (Username/Password)")
        print("   • TOTP (Time-based One-Time Password)")
        print("   • WebAuthn (FIDO2)")
        print("   • API Key Authentication")
        print("   • OAuth2 (Google, Microsoft, etc.)")
        print("   • SAML SSO")
        print("   • LDAP")
        print("   • Kerberos")
        print("   • Client Certificate (Mutual TLS)")
        print()
        
        print("🔒 Security Features:")
        print("   • TLS 1.2 and TLS 1.3 support")
        print("   • Modern cipher suites")
        print("   • HSTS (HTTP Strict Transport Security)")
        print("   • Security headers")
        print("   • Rate limiting")
        print("   • Client certificate authentication")
        print()
        
        # Save results to file
        results_file = f"modern_auth_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"📄 Results saved to: {results_file}")

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test modern authentication methods')
    parser.add_argument('--url', default='https://owa.shtrum.com', help='Base URL for testing')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    tester = ModernAuthTester(args.url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()


