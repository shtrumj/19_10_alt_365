#!/usr/bin/env python3
"""
365 Email System - Main entry point
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    print("Starting 365 Email System...")
    print("SMTP Server: localhost:1026 (non-privileged port)")
    print("Web Interface: http://localhost:8001/owa")
    print("API Documentation: http://localhost:8001/docs")
    print("ActiveSync: http://localhost:8001/activesync")
    print("")
    print("To run SMTP on port 25 (requires root): sudo python run_smtp25.py")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
