"""
Deep debugging router for Outlook communication analysis
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any
import uuid

router = APIRouter()

# Store communication logs in memory for analysis
communication_logs = []

def log_communication(event_type: str, request: Request, response_data: Dict[str, Any] = None):
    """Log detailed communication between Outlook and server"""
    timestamp = datetime.utcnow().isoformat()
    request_id = str(uuid.uuid4())
    
    # Extract request details
    request_details = {
        "timestamp": timestamp,
        "request_id": request_id,
        "event_type": event_type,
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
        "content_type": request.headers.get("content-type", ""),
        "content_length": request.headers.get("content-length", "0"),
        "authorization": request.headers.get("authorization", ""),
        "host": request.headers.get("host", ""),
        "x_forwarded_for": request.headers.get("x-forwarded-for", ""),
        "x_real_ip": request.headers.get("x-real-ip", ""),
    }
    
    # Add response data if provided
    if response_data:
        request_details["response"] = response_data
    
    # Store in memory logs
    communication_logs.append(request_details)
    
    # Keep only last 1000 entries
    if len(communication_logs) > 1000:
        communication_logs.pop(0)
    
    # Log to file
    logger = logging.getLogger(__name__)
    logger.info(f"OUTLOOK_DEBUG: {json.dumps(request_details, indent=2)}")
    
    return request_details

@router.get("/debug/communication")
async def get_communication_logs():
    """Get all communication logs for analysis"""
    return {
        "total_logs": len(communication_logs),
        "logs": communication_logs[-50:]  # Return last 50 entries
    }

@router.get("/debug/outlook-requests")
async def get_outlook_requests():
    """Get only Outlook-specific requests"""
    outlook_logs = []
    for log in communication_logs:
        user_agent = log.get("user_agent", "").lower()
        if any(keyword in user_agent for keyword in ["outlook", "microsoft office", "mapi"]):
            outlook_logs.append(log)
    
    return {
        "outlook_requests": len(outlook_logs),
        "logs": outlook_logs[-20:]  # Return last 20 Outlook requests
    }

@router.get("/debug/authentication-flow")
async def get_authentication_flow():
    """Analyze authentication flow"""
    auth_logs = []
    for log in communication_logs:
        if log.get("authorization") or "auth" in log.get("event_type", "").lower():
            auth_logs.append(log)
    
    return {
        "auth_requests": len(auth_logs),
        "logs": auth_logs[-20:]
    }

@router.get("/debug/ntlm-analysis")
async def analyze_ntlm_flow():
    """Analyze NTLM authentication flow"""
    ntlm_logs = []
    for log in communication_logs:
        auth_header = log.get("authorization", "")
        if "ntlm" in auth_header.lower():
            ntlm_logs.append(log)
    
    # Analyze NTLM flow
    type1_requests = [log for log in ntlm_logs if "TlRMTVNTUAAB" in log.get("authorization", "")]
    type3_requests = [log for log in ntlm_logs if "TlRMTVNTUAAD" in log.get("authorization", "")]
    
    return {
        "total_ntlm_requests": len(ntlm_logs),
        "type1_requests": len(type1_requests),
        "type3_requests": len(type3_requests),
        "ntlm_logs": ntlm_logs[-10:],
        "type1_logs": type1_requests[-5:],
        "type3_logs": type3_requests[-5:]
    }

@router.get("/debug/clear-logs")
async def clear_logs():
    """Clear communication logs"""
    global communication_logs
    communication_logs.clear()
    return {"message": "Logs cleared"}

# Note: Middleware moved to main.py since APIRouter doesn't support middleware directly
