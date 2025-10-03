#!/usr/bin/env python3
"""
Test SMTP server on port 25
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.smtp_server import start_smtp_server_25, stop_smtp_server_25

async def test_smtp25():
    """Test SMTP server on port 25"""
    try:
        print("Testing SMTP server on port 25...")
        await start_smtp_server_25()
        print("SMTP server started successfully on port 25")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        print("Stopping SMTP server...")
        await stop_smtp_server_25()
        print("SMTP server stopped")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_smtp25())
