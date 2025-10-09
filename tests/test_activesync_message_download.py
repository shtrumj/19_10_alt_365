#!/usr/bin/env python3
"""
ActiveSync Message Download Test
Tests ActiveSync protocol implementation according to Microsoft documentation
"""

import requests
import base64
import xml.etree.ElementTree as ET
from datetime import datetime
import json

class ActiveSyncTester:
    def __init__(self, base_url="https://owa.shtrum.com", username="yonatan", password="Gib$0n579!"):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False
        
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Set up Basic Auth
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {encoded_credentials}',
            'User-Agent': 'Microsoft-Server-ActiveSync/16.0',
            'MS-ASProtocolVersion': '16.1',
            'Content-Type': 'application/vnd.ms-sync.wbxml'
        })
    
    def test_options_discovery(self):
        """Test ActiveSync OPTIONS discovery"""
        print("🔍 Testing ActiveSync OPTIONS Discovery...")
        
        url = f"{self.base_url}/activesync/Microsoft-Server-ActiveSync"
        response = self.session.options(url)
        
        print(f"   Status: {response.status_code}")
        print(f"   MS-Server-ActiveSync: {response.headers.get('ms-server-activesync', 'N/A')}")
        print(f"   MS-ASProtocolVersions: {response.headers.get('ms-asprotocolversions', 'N/A')}")
        print(f"   MS-ASProtocolCommands: {response.headers.get('ms-asprotocolcommands', 'N/A')}")
        
        if response.status_code == 200:
            print("   ✅ OPTIONS discovery successful")
            return True
        else:
            print(f"   ❌ OPTIONS discovery failed: {response.status_code}")
            return False
    
    def test_foldersync(self):
        """Test ActiveSync FolderSync command"""
        print("\n📁 Testing ActiveSync FolderSync...")
        
        url = f"{self.base_url}/activesync/Microsoft-Server-ActiveSync"
        params = {
            'Cmd': 'FolderSync',
            'DeviceId': 'test-device-001',
            'DeviceType': 'SmartPhone',
            'SyncKey': '0'  # Initial sync
        }
        
        response = self.session.post(url, params=params)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        if response.status_code == 200:
            print("   ✅ FolderSync successful")
            # Parse XML response
            try:
                root = ET.fromstring(response.text)
                # Handle XML namespaces properly
                status = root.find('Status')
                if status is None:
                    status = root.find('{FolderHierarchy:}Status')
                if status is None:
                    status = root.find('{AirSync}Status')
                
                sync_key = root.find('SyncKey')
                if sync_key is None:
                    sync_key = root.find('{FolderHierarchy:}SyncKey')
                if sync_key is None:
                    sync_key = root.find('{AirSync}SyncKey')
                
                changes = root.find('Changes')
                if changes is None:
                    changes = root.find('{FolderHierarchy:}Changes')
                if changes is None:
                    changes = root.find('{AirSync}Changes')
                
                print(f"   Status: {status.text if status is not None else 'N/A'}")
                print(f"   SyncKey: {sync_key.text if sync_key is not None else 'N/A'}")
                print(f"   Changes: {len(changes) if changes is not None else 0} items")
                
                return sync_key.text if sync_key is not None else None
            except ET.ParseError as e:
                print(f"   ⚠️ XML parsing error: {e}")
                return None
        else:
            print(f"   ❌ FolderSync failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return None
    
    def test_sync_initial(self, sync_key):
        """Test ActiveSync Sync command for initial sync"""
        print(f"\n📧 Testing ActiveSync Sync (Initial) with SyncKey: 0...")
        
        url = f"{self.base_url}/activesync/Microsoft-Server-ActiveSync"
        params = {
            'Cmd': 'Sync',
            'DeviceId': 'test-device-001',
            'DeviceType': 'SmartPhone',
            'CollectionId': '1',  # Inbox
            'SyncKey': '0'  # Use SyncKey=0 for initial sync
        }
        
        response = self.session.post(url, params=params)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("   ✅ Sync successful")
            # Parse XML response
            try:
                root = ET.fromstring(response.text)
                status = root.find('Status')
                
                print(f"   Status: {status.text if status is not None else 'N/A'}")
                
                # Look for Collection elements (with or without namespace)
                collections = root.findall('.//Collection') or root.findall('.//{AirSync}Collection')
                
                if collections:
                    for collection in collections:
                        collection_id = collection.get('CollectionId', 'N/A')
                        sync_key_elem = collection.get('SyncKey', 'N/A')
                        print(f"   Collection {collection_id} SyncKey: {sync_key_elem}")
                        
                        # Count email items
                        email_count = 0
                        for item in collection:
                            if item.tag == 'Add' or item.tag == '{AirSync}Add':
                                email_count += 1
                                server_id = item.get('ServerId', 'N/A')
                                print(f"     📧 Email {email_count}: ServerId={server_id}")
                                
                                # Get email details
                                app_data = item.find('ApplicationData') or item.find('{AirSync}ApplicationData')
                                if app_data is not None:
                                    subject = app_data.find('Subject') or app_data.find('{AirSync}Subject')
                                    from_elem = app_data.find('From') or app_data.find('{AirSync}From')
                                    date_received = app_data.find('DateReceived') or app_data.find('{AirSync}DateReceived')
                                    
                                    print(f"       Subject: {subject.text if subject is not None else 'N/A'}")
                                    print(f"       From: {from_elem.text if from_elem is not None else 'N/A'}")
                                    print(f"       Date: {date_received.text if date_received is not None else 'N/A'}")
                        
                        print(f"   📊 Total emails in sync: {email_count}")
                        return sync_key_elem, email_count
                else:
                    print("   ⚠️ No collections found in response")
                    return None, 0
                    
            except ET.ParseError as e:
                print(f"   ⚠️ XML parsing error: {e}")
                print(f"   Raw response: {response.text[:500]}...")
                return None, 0
        else:
            print(f"   ❌ Sync failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return None, 0
    
    def test_sync_incremental(self, sync_key):
        """Test ActiveSync Sync command for incremental sync"""
        print(f"\n🔄 Testing ActiveSync Sync (Incremental) with SyncKey: {sync_key}...")
        
        url = f"{self.base_url}/activesync/Microsoft-Server-ActiveSync"
        params = {
            'Cmd': 'Sync',
            'DeviceId': 'test-device-001',
            'DeviceType': 'SmartPhone',
            'CollectionId': '1',  # Inbox
            'SyncKey': sync_key
        }
        
        response = self.session.post(url, params=params)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("   ✅ Incremental sync successful")
            # Parse XML response
            try:
                root = ET.fromstring(response.text)
                status = root.find('Status')
                
                print(f"   Status: {status.text if status is not None else 'N/A'}")
                
                if status is not None and status.text == "1":
                    print("   📭 No new changes (client up to date)")
                    return True
                else:
                    print("   📧 New changes available")
                    return True
                    
            except ET.ParseError as e:
                print(f"   ⚠️ XML parsing error: {e}")
                return False
        else:
            print(f"   ❌ Incremental sync failed: {response.status_code}")
            return False
    
    def test_getitemestimate(self):
        """Test ActiveSync GetItemEstimate command"""
        print("\n📊 Testing ActiveSync GetItemEstimate...")
        
        url = f"{self.base_url}/activesync/Microsoft-Server-ActiveSync"
        params = {
            'Cmd': 'GetItemEstimate',
            'DeviceId': 'test-device-001',
            'DeviceType': 'SmartPhone',
            'CollectionId': '1'  # Inbox
        }
        
        response = self.session.post(url, params=params)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ GetItemEstimate successful")
            try:
                root = ET.fromstring(response.text)
                status = root.find('Status')
                response_elem = root.find('Response')
                
                print(f"   Status: {status.text if status is not None else 'N/A'}")
                
                if response_elem is not None:
                    collection = response_elem.find('Collection')
                    if collection is not None:
                        collection_id = collection.get('CollectionId', 'N/A')
                        estimate = collection.find('Estimate')
                        print(f"   Collection {collection_id} Estimate: {estimate.text if estimate is not None else 'N/A'}")
                
                return True
            except ET.ParseError as e:
                print(f"   ⚠️ XML parsing error: {e}")
                return False
        else:
            print(f"   ❌ GetItemEstimate failed: {response.status_code}")
            return False
    
    def run_comprehensive_test(self):
        """Run comprehensive ActiveSync test"""
        print("🚀 ACTIVESYNC MESSAGE DOWNLOAD COMPREHENSIVE TEST")
        print("=" * 60)
        print(f"Timestamp: {datetime.now()}")
        print(f"Server: {self.base_url}")
        print(f"User: {self.username}")
        print()
        
        results = {}
        
        # Test 1: OPTIONS Discovery
        results['options'] = self.test_options_discovery()
        
        # Test 2: FolderSync
        sync_key = self.test_foldersync()
        results['foldersync'] = sync_key is not None
        
        if sync_key:
            # Test 3: Initial Sync
            sync_result = self.test_sync_initial(sync_key)
            if sync_result:
                new_sync_key, email_count = sync_result
                results['sync_initial'] = new_sync_key is not None
                results['email_count'] = email_count
                
                if new_sync_key:
                    # Test 4: Incremental Sync
                    results['sync_incremental'] = self.test_sync_incremental(new_sync_key)
            else:
                results['sync_initial'] = False
                results['email_count'] = 0
        
        # Test 5: GetItemEstimate
        results['getitemestimate'] = self.test_getitemestimate()
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        for test, result in results.items():
            if test == 'email_count':
                print(f"📧 Emails Downloaded: {result}")
            else:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{test.replace('_', ' ').title()}: {status}")
        
        # Overall result
        critical_tests = ['options', 'foldersync', 'sync_initial']
        passed_critical = sum(1 for test in critical_tests if results.get(test, False))
        
        print(f"\n🎯 Overall Result: {passed_critical}/{len(critical_tests)} critical tests passed")
        
        if passed_critical == len(critical_tests):
            print("✅ ActiveSync message download is working correctly!")
        else:
            print("❌ ActiveSync message download has issues that need to be fixed.")
        
        return results

def main():
    tester = ActiveSyncTester()
    results = tester.run_comprehensive_test()
    
    # Save results to file
    with open('activesync_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Results saved to: activesync_test_results.json")

if __name__ == "__main__":
    main()
