#!/usr/bin/env python3
"""
Debug SMTP server configuration
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.smtp_server import EmailHandler
from aiosmtpd.controller import Controller
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_smtp_controller():
    """Test SMTP controller with handler"""
    try:
        print("Creating EmailHandler...")
        handler = EmailHandler()
        print("✅ Handler created")
        
        print("Creating Controller...")
        controller = Controller(handler, hostname='0.0.0.0', port=25)
        print("✅ Controller created")
        
        print("Starting controller...")
        controller.start()
        print("✅ Controller started")
        
        print("Controller is running. Press Ctrl+C to stop...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping controller...")
            controller.stop()
            print("✅ Controller stopped")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smtp_controller())
