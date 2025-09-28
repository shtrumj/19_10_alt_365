#!/usr/bin/env python3
"""
Deep WebSocket Analysis Script
Analyzes WebSocket connection issues with detailed logging
"""
import asyncio
import websockets
import json
import time
import sys
import os
from datetime import datetime

class WebSocketAnalyzer:
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.results.append(log_entry)
        
    async def test_websocket_connection(self, url, test_name):
        """Test WebSocket connection with detailed analysis"""
        self.log(f"🧪 Starting {test_name}")
        self.log(f"🔗 Testing URL: {url}")
        
        try:
            self.log(f"📡 Attempting WebSocket connection...")
            start_time = time.time()
            
            async with websockets.connect(url) as websocket:
                connection_time = time.time() - start_time
                self.log(f"✅ Connection successful! Time: {connection_time:.3f}s")
                
                # Test message exchange
                self.log(f"📤 Sending test message...")
                test_message = f"Test message from {test_name} at {datetime.now()}"
                await websocket.send(test_message)
                
                self.log(f"📥 Waiting for response...")
                response = await websocket.recv()
                self.log(f"📨 Received response: {response}")
                
                # Test JSON message
                self.log(f"📤 Sending JSON test message...")
                json_message = {
                    "type": "test",
                    "timestamp": datetime.now().isoformat(),
                    "test_name": test_name
                }
                await websocket.send(json.dumps(json_message))
                
                self.log(f"📥 Waiting for JSON response...")
                json_response = await websocket.recv()
                self.log(f"📨 Received JSON response: {json_response}")
                
                self.log(f"✅ {test_name} completed successfully")
                return True
                
        except websockets.exceptions.ConnectionClosed as e:
            self.log(f"❌ {test_name} failed - Connection closed: {e.code} - {e.reason}", "ERROR")
            return False
        except websockets.exceptions.InvalidURI as e:
            self.log(f"❌ {test_name} failed - Invalid URI: {e}", "ERROR")
            return False
        except websockets.exceptions.InvalidHandshake as e:
            self.log(f"❌ {test_name} failed - Invalid handshake: {e}", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ {test_name} failed - Unexpected error: {e}", "ERROR")
            return False
    
    async def analyze_websocket_issues(self):
        """Comprehensive WebSocket analysis"""
        self.log("🔍 Starting Deep WebSocket Analysis")
        self.log(f"🕐 Analysis started at: {self.start_time}")
        
        # Test different WebSocket endpoints
        tests = [
            {
                "url": "ws://localhost:8001/ws/email-notifications/1",
                "name": "Main App WebSocket (Port 8001)"
            },
            {
                "url": "ws://localhost:8002/test-ws", 
                "name": "Minimal WebSocket (Port 8002)"
            },
            {
                "url": "ws://localhost:8003/ws/email-notifications/1",
                "name": "Isolated WebSocket (Port 8003)"
            }
        ]
        
        results = {}
        
        for test in tests:
            self.log(f"\n{'='*60}")
            self.log(f"🧪 Testing: {test['name']}")
            self.log(f"{'='*60}")
            
            result = await self.test_websocket_connection(test['url'], test['name'])
            results[test['name']] = result
            
            # Wait between tests
            await asyncio.sleep(1)
        
        # Analysis summary
        self.log(f"\n{'='*60}")
        self.log("📊 ANALYSIS SUMMARY")
        self.log(f"{'='*60}")
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{status} - {test_name}")
        
        # Recommendations
        self.log(f"\n💡 RECOMMENDATIONS:")
        if results.get("Main App WebSocket (Port 8001)", False):
            self.log("✅ Main app WebSocket is working - no issues detected")
        else:
            self.log("❌ Main app WebSocket failing - check authentication/configuration")
            
        if results.get("Minimal WebSocket (Port 8002)", False):
            self.log("✅ Minimal WebSocket working - basic functionality OK")
        else:
            self.log("❌ Minimal WebSocket failing - check basic setup")
            
        if results.get("Isolated WebSocket (Port 8003)", False):
            self.log("✅ Isolated WebSocket working - router implementation OK")
        else:
            self.log("❌ Isolated WebSocket failing - check router configuration")
        
        # Save results to file
        self.save_results()
        
    def save_results(self):
        """Save analysis results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"websocket_analysis_{timestamp}.log"
        
        with open(filename, 'w') as f:
            f.write(f"WebSocket Deep Analysis Report\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"{'='*60}\n\n")
            
            for result in self.results:
                f.write(result + "\n")
        
        self.log(f"📄 Results saved to: {filename}")

async def main():
    """Main analysis function"""
    analyzer = WebSocketAnalyzer()
    await analyzer.analyze_websocket_issues()

if __name__ == "__main__":
    print("🔍 WebSocket Deep Analysis Tool")
    print("=" * 50)
    asyncio.run(main())
