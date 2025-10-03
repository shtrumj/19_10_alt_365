#!/usr/bin/env python3
"""
Comprehensive MS-ASCMD Test Suite
Tests all ActiveSync commands according to official Microsoft MS-ASCMD specification
"""

import requests
import json
import time
from datetime import datetime
import xml.etree.ElementTree as ET

class MSASCMDTestSuite:
    def __init__(self, server_url="https://owa.shtrum.com", username="yonatan", password="Gib$0n579!"):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.results = {}
        
    def test_options_discovery(self):
        """Test OPTIONS discovery according to MS-ASCMD"""
        print("🔍 Testing MS-ASCMD OPTIONS Discovery...")
        
        try:
            response = self.session.options(f"{self.server_url}/activesync/Microsoft-Server-ActiveSync")
            
            self.results['options'] = {
                'status': response.status_code,
                'headers': dict(response.headers),
                'success': response.status_code == 200
            }
            
            # Check for required MS-ASCMD headers
            required_headers = [
                'MS-Server-ActiveSync',
                'MS-ASProtocolVersions', 
                'MS-ASProtocolCommands',
                'MS-ASProtocolSupports'
            ]
            
            missing_headers = [h for h in required_headers if h not in response.headers]
            if missing_headers:
                print(f"   ❌ Missing required headers: {missing_headers}")
                self.results['options']['success'] = False
            else:
                print(f"   ✅ All required MS-ASCMD headers present")
                print(f"   📊 MS-Server-ActiveSync: {response.headers.get('MS-Server-ActiveSync')}")
                print(f"   📊 MS-ASProtocolVersions: {response.headers.get('MS-ASProtocolVersions')}")
                print(f"   📊 MS-ASProtocolCommands: {response.headers.get('MS-ASProtocolCommands')}")
            
            return self.results['options']['success']
            
        except Exception as e:
            print(f"   ❌ OPTIONS test failed: {e}")
            self.results['options'] = {'success': False, 'error': str(e)}
            return False
    
    def test_foldersync(self):
        """Test FolderSync command according to MS-ASCMD"""
        print("📁 Testing MS-ASCMD FolderSync...")
        
        try:
            params = {
                'Cmd': 'FolderSync',
                'SyncKey': '0',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['foldersync'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                # Parse XML response
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{FolderHierarchy:}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    sync_key = root.find('.//{AirSync}SyncKey')
                    if sync_key is None:
                        sync_key = root.find('.//{FolderHierarchy:}SyncKey')
                    if sync_key is None:
                        sync_key = root.find('.//SyncKey')
                    
                    if status is not None:
                        self.results['foldersync']['xml_status'] = status.text
                        print(f"   ✅ FolderSync successful")
                        print(f"   📊 Status: {status.text}")
                        if sync_key is not None:
                            print(f"   📊 SyncKey: {sync_key.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['foldersync']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['foldersync']['success'] = False
            else:
                print(f"   ❌ FolderSync failed with status {response.status_code}")
                self.results['foldersync']['success'] = False
                
            return self.results['foldersync']['success']
            
        except Exception as e:
            print(f"   ❌ FolderSync test failed: {e}")
            self.results['foldersync'] = {'success': False, 'error': str(e)}
            return False
    
    def test_sync(self):
        """Test Sync command according to MS-ASCMD"""
        print("📧 Testing MS-ASCMD Sync...")
        
        try:
            params = {
                'Cmd': 'Sync',
                'SyncKey': '0',
                'CollectionId': '1',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['sync'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{FolderHierarchy:}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['sync']['xml_status'] = status.text
                        print(f"   ✅ Sync successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['sync']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['sync']['success'] = False
            else:
                print(f"   ❌ Sync failed with status {response.status_code}")
                self.results['sync']['success'] = False
                
            return self.results['sync']['success']
            
        except Exception as e:
            print(f"   ❌ Sync test failed: {e}")
            self.results['sync'] = {'success': False, 'error': str(e)}
            return False
    
    def test_getitemestimate(self):
        """Test GetItemEstimate command according to MS-ASCMD"""
        print("📊 Testing MS-ASCMD GetItemEstimate...")
        
        try:
            params = {
                'Cmd': 'GetItemEstimate',
                'CollectionId': '1',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['getitemestimate'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    estimate = root.find('.//{AirSync}Estimate')
                    if estimate is None:
                        estimate = root.find('.//Estimate')
                    
                    if status is not None:
                        self.results['getitemestimate']['xml_status'] = status.text
                        print(f"   ✅ GetItemEstimate successful")
                        print(f"   📊 Status: {status.text}")
                        if estimate is not None:
                            print(f"   📊 Estimate: {estimate.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['getitemestimate']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['getitemestimate']['success'] = False
            else:
                print(f"   ❌ GetItemEstimate failed with status {response.status_code}")
                self.results['getitemestimate']['success'] = False
                
            return self.results['getitemestimate']['success']
            
        except Exception as e:
            print(f"   ❌ GetItemEstimate test failed: {e}")
            self.results['getitemestimate'] = {'success': False, 'error': str(e)}
            return False
    
    def test_provision(self):
        """Test Provision command according to MS-ASCMD"""
        print("🔐 Testing MS-ASCMD Provision...")
        
        try:
            params = {
                'Cmd': 'Provision',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['provision'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['provision']['xml_status'] = status.text
                        print(f"   ✅ Provision successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['provision']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['provision']['success'] = False
            else:
                print(f"   ❌ Provision failed with status {response.status_code}")
                self.results['provision']['success'] = False
                
            return self.results['provision']['success']
            
        except Exception as e:
            print(f"   ❌ Provision test failed: {e}")
            self.results['provision'] = {'success': False, 'error': str(e)}
            return False
    
    def test_settings(self):
        """Test Settings command according to MS-ASCMD"""
        print("⚙️ Testing MS-ASCMD Settings...")
        
        try:
            params = {
                'Cmd': 'Settings',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['settings'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['settings']['xml_status'] = status.text
                        print(f"   ✅ Settings successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['settings']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['settings']['success'] = False
            else:
                print(f"   ❌ Settings failed with status {response.status_code}")
                self.results['settings']['success'] = False
                
            return self.results['settings']['success']
            
        except Exception as e:
            print(f"   ❌ Settings test failed: {e}")
            self.results['settings'] = {'success': False, 'error': str(e)}
            return False
    
    def test_search(self):
        """Test Search command according to MS-ASCMD"""
        print("🔍 Testing MS-ASCMD Search...")
        
        try:
            params = {
                'Cmd': 'Search',
                'Query': 'test',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['search'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['search']['xml_status'] = status.text
                        print(f"   ✅ Search successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['search']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['search']['success'] = False
            else:
                print(f"   ❌ Search failed with status {response.status_code}")
                self.results['search']['success'] = False
                
            return self.results['search']['success']
            
        except Exception as e:
            print(f"   ❌ Search test failed: {e}")
            self.results['search'] = {'success': False, 'error': str(e)}
            return False
    
    def test_itemoperations(self):
        """Test ItemOperations command according to MS-ASCMD"""
        print("📋 Testing MS-ASCMD ItemOperations...")
        
        try:
            params = {
                'Cmd': 'ItemOperations',
                'ItemId': '1',
                'CollectionId': '1',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['itemoperations'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['itemoperations']['xml_status'] = status.text
                        print(f"   ✅ ItemOperations successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['itemoperations']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['itemoperations']['success'] = False
            else:
                print(f"   ❌ ItemOperations failed with status {response.status_code}")
                self.results['itemoperations']['success'] = False
                
            return self.results['itemoperations']['success']
            
        except Exception as e:
            print(f"   ❌ ItemOperations test failed: {e}")
            self.results['itemoperations'] = {'success': False, 'error': str(e)}
            return False
    
    def test_resolverecipients(self):
        """Test ResolveRecipients command according to MS-ASCMD"""
        print("👥 Testing MS-ASCMD ResolveRecipients...")
        
        try:
            params = {
                'Cmd': 'ResolveRecipients',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['resolverecipients'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['resolverecipients']['xml_status'] = status.text
                        print(f"   ✅ ResolveRecipients successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['resolverecipients']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['resolverecipients']['success'] = False
            else:
                print(f"   ❌ ResolveRecipients failed with status {response.status_code}")
                self.results['resolverecipients']['success'] = False
                
            return self.results['resolverecipients']['success']
            
        except Exception as e:
            print(f"   ❌ ResolveRecipients test failed: {e}")
            self.results['resolverecipients'] = {'success': False, 'error': str(e)}
            return False
    
    def test_validatecert(self):
        """Test ValidateCert command according to MS-ASCMD"""
        print("🔒 Testing MS-ASCMD ValidateCert...")
        
        try:
            params = {
                'Cmd': 'ValidateCert',
                'DeviceId': 'test-device',
                'DeviceType': 'SmartPhone'
            }
            
            response = self.session.post(
                f"{self.server_url}/activesync/Microsoft-Server-ActiveSync",
                params=params
            )
            
            self.results['validatecert'] = {
                'status': response.status_code,
                'content_type': response.headers.get('Content-Type'),
                'success': response.status_code == 200
            }
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Handle XML namespaces properly - try different namespaces
                    status = root.find('.//{AirSync}Status')
                    if status is None:
                        status = root.find('.//{Provision:}Status')
                    if status is None:
                        status = root.find('.//{Settings}Status')
                    if status is None:
                        status = root.find('.//{Search}Status')
                    if status is None:
                        status = root.find('.//{ItemOperations}Status')
                    if status is None:
                        status = root.find('.//{ResolveRecipients}Status')
                    if status is None:
                        status = root.find('.//{ValidateCert}Status')
                    if status is None:
                        status = root.find('.//Status')
                    
                    if status is not None:
                        self.results['validatecert']['xml_status'] = status.text
                        print(f"   ✅ ValidateCert successful")
                        print(f"   📊 Status: {status.text}")
                    else:
                        print(f"   ❌ Invalid XML response - no Status element")
                        self.results['validatecert']['success'] = False
                        
                except ET.ParseError as e:
                    print(f"   ❌ XML parsing error: {e}")
                    self.results['validatecert']['success'] = False
            else:
                print(f"   ❌ ValidateCert failed with status {response.status_code}")
                self.results['validatecert']['success'] = False
                
            return self.results['validatecert']['success']
            
        except Exception as e:
            print(f"   ❌ ValidateCert test failed: {e}")
            self.results['validatecert'] = {'success': False, 'error': str(e)}
            return False
    
    def run_comprehensive_test(self):
        """Run comprehensive MS-ASCMD test suite"""
        print("🚀 COMPREHENSIVE MS-ASCMD TEST SUITE")
        print("=" * 60)
        print(f"Timestamp: {datetime.now()}")
        print(f"Server: {self.server_url}")
        print(f"User: {self.username}")
        print()
        
        # Test all MS-ASCMD commands
        tests = [
            self.test_options_discovery,
            self.test_foldersync,
            self.test_sync,
            self.test_getitemestimate,
            self.test_provision,
            self.test_settings,
            self.test_search,
            self.test_itemoperations,
            self.test_resolverecipients,
            self.test_validatecert
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
            except Exception as e:
                print(f"   ❌ Test failed with exception: {e}")
            print()
        
        # Summary
        print("=" * 60)
        print("📋 COMPREHENSIVE TEST SUMMARY")
        print("=" * 60)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            print(f"{test_name.capitalize()}: {status}")
        
        print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All MS-ASCMD tests passed! Full compliance achieved.")
        else:
            print("⚠️ Some MS-ASCMD tests failed. Review implementation.")
        
        # Save results
        with open('ms_ascmd_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Results saved to: ms_ascmd_test_results.json")
        
        return passed == total

if __name__ == "__main__":
    test_suite = MSASCMDTestSuite()
    success = test_suite.run_comprehensive_test()
    exit(0 if success else 1)
