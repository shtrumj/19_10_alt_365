#!/usr/bin/env python3
"""
Startup script to run both main app and standalone WebSocket server
"""
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutting down servers...")
    sys.exit(0)

def start_websocket_server():
    """Start the standalone WebSocket server"""
    print("🚀 Starting standalone WebSocket server on port 8004...")
    try:
        # Change to app directory
        os.chdir('/app')
        
        # Start WebSocket server
        process = subprocess.Popen([
            sys.executable, 'app/websocket_server.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print("✅ WebSocket server started successfully!")
        return process
    except Exception as e:
        print(f"❌ Error starting WebSocket server: {e}")
        return None

def main():
    """Main startup function"""
    print("🔧 Starting 365 Email System with standalone WebSocket server...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start WebSocket server
    websocket_process = start_websocket_server()
    
    if websocket_process:
        print("🎉 Both servers are running!")
        print("📡 Main app: http://localhost:8001")
        print("🔗 WebSocket server: http://localhost:8004")
        print("🌐 Web interface: https://owa.shtrum.com")
        
        try:
            # Keep the script running
            websocket_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            websocket_process.terminate()
            websocket_process.wait()
    else:
        print("❌ Failed to start WebSocket server")
        sys.exit(1)

if __name__ == "__main__":
    main()
