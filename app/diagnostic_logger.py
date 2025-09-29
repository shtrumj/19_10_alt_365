#!/usr/bin/env python3
"""
Enhanced Diagnostic Logger for Outlook Debugging

This module provides comprehensive logging capabilities for debugging
Outlook auto-configuration and connection issues.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Create logs directory structure
LOGS_BASE = os.environ.get('LOGS_DIR', 'logs')
LOG_DIRS = [
    'web/mapi',
    'web/autodiscover', 
    'web/ews',
    'activesync',
    'smtp',
    'diagnostics',
    'outlook_debug'
]

for log_dir in LOG_DIRS:
    os.makedirs(os.path.join(LOGS_BASE, log_dir), exist_ok=True)

def _write_json_line(log_file: str, data: Dict[str, Any]):
    """Write a JSON log line to the specified file"""
    try:
        full_path = os.path.join(LOGS_BASE, log_file)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            **data
        }
        
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Error writing log: {e}")

class OutlookDiagnosticLogger:
    """Enhanced diagnostic logger for Outlook debugging"""
    
    def __init__(self):
        self.session_logs = {}
    
    def log_outlook_phase(self, phase: str, details: Dict[str, Any], user_agent: str = None):
        """Log Outlook configuration phases"""
        log_data = {
            "component": "outlook_diagnostics",
            "phase": phase,
            "details": details
        }
        
        if user_agent:
            log_data["user_agent"] = user_agent
        
        _write_json_line("outlook_debug/phases.log", log_data)
    
    def log_protocol_attempt(self, protocol: str, success: bool, details: Dict[str, Any]):
        """Log protocol connection attempts"""
        log_data = {
            "component": "protocol_diagnostics",
            "protocol": protocol,
            "success": success,
            "details": details
        }
        
        _write_json_line("outlook_debug/protocols.log", log_data)
    
    def log_authentication_flow(self, auth_type: str, stage: str, success: bool, details: Dict[str, Any]):
        """Log authentication flow details"""
        log_data = {
            "component": "auth_diagnostics", 
            "auth_type": auth_type,
            "stage": stage,
            "success": success,
            "details": details
        }
        
        _write_json_line("outlook_debug/authentication.log", log_data)
    
    def log_mapi_rpc_details(self, operation: str, session_id: str, request_data: bytes, response_data: bytes = None):
        """Log detailed MAPI RPC operations"""
        log_data = {
            "component": "mapi_rpc_diagnostics",
            "operation": operation,
            "session_id": session_id,
            "request_length": len(request_data),
            "request_hex": request_data[:64].hex() if request_data else "",
            "response_length": len(response_data) if response_data else 0,
            "response_hex": response_data[:64].hex() if response_data else ""
        }
        
        _write_json_line("outlook_debug/mapi_rpc.log", log_data)
    
    def log_error_with_context(self, error_type: str, error_message: str, context: Dict[str, Any]):
        """Log errors with full context"""
        log_data = {
            "component": "error_diagnostics",
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
            "timestamp": time.time()
        }
        
        _write_json_line("outlook_debug/errors.log", log_data)
    
    def start_session_tracking(self, session_id: str, user_email: str, user_agent: str):
        """Start tracking an Outlook session"""
        self.session_logs[session_id] = {
            "start_time": time.time(),
            "user_email": user_email,
            "user_agent": user_agent,
            "phases": [],
            "protocols_attempted": [],
            "errors": []
        }
        
        self.log_outlook_phase("session_start", {
            "session_id": session_id,
            "user_email": user_email
        }, user_agent)
    
    def add_session_phase(self, session_id: str, phase: str, success: bool, details: Dict[str, Any]):
        """Add a phase to session tracking"""
        if session_id in self.session_logs:
            self.session_logs[session_id]["phases"].append({
                "phase": phase,
                "success": success,
                "timestamp": time.time(),
                "details": details
            })
        
        self.log_outlook_phase(phase, {
            "session_id": session_id,
            "success": success,
            **details
        })
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session for debugging"""
        if session_id not in self.session_logs:
            return {"error": "Session not found"}
        
        session = self.session_logs[session_id]
        return {
            "session_id": session_id,
            "duration": time.time() - session["start_time"],
            "user_email": session["user_email"],
            "user_agent": session["user_agent"],
            "phases_completed": len([p for p in session["phases"] if p["success"]]),
            "total_phases": len(session["phases"]),
            "errors_count": len(session["errors"]),
            "last_phase": session["phases"][-1] if session["phases"] else None
        }

# Global diagnostic logger instance
outlook_diagnostics = OutlookDiagnosticLogger()

def log_autodiscover_request(request_type: str, email: str, user_agent: str, success: bool, details: Dict[str, Any]):
    """Log autodiscover requests with enhanced details"""
    outlook_diagnostics.log_protocol_attempt("autodiscover", success, {
        "request_type": request_type,
        "email": email,
        "user_agent": user_agent,
        **details
    })

def log_mapi_request(operation: str, session_id: str, user_agent: str, success: bool, details: Dict[str, Any]):
    """Log MAPI requests with enhanced details"""
    outlook_diagnostics.log_protocol_attempt("mapi_http", success, {
        "operation": operation,
        "session_id": session_id,
        "user_agent": user_agent,
        **details
    })

def log_ews_request(operation: str, user_agent: str, success: bool, details: Dict[str, Any]):
    """Log EWS requests with enhanced details"""
    outlook_diagnostics.log_protocol_attempt("ews", success, {
        "operation": operation,
        "user_agent": user_agent,
        **details
    })

def log_outlook_connection_issue(issue_type: str, description: str, context: Dict[str, Any]):
    """Log specific Outlook connection issues"""
    outlook_diagnostics.log_error_with_context(
        "outlook_connection_issue",
        f"{issue_type}: {description}",
        context
    )

def log_autodiscover(event: str, details: Dict[str, Any]):
    """Log autodiscover events (backward compatibility)"""
    _write_json_line("web/autodiscover/autodiscover.log", {
        "component": "autodiscover",
        "event": event,
        "details": details
    })

def log_ews(event: str, details: Dict[str, Any]):
    """Log EWS events (backward compatibility)"""
    _write_json_line("web/ews/ews.log", {
        "component": "ews",
        "event": event,
        "details": details
    })

def log_mapi(event: str, details: Dict[str, Any]):
    """Log MAPI events (backward compatibility)"""
    _write_json_line("web/mapi/mapi.log", {
        "event": event,
        **details
    })

def create_debug_summary() -> str:
    """Create a debug summary for troubleshooting"""
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system_status": "operational",
        "active_sessions": len(outlook_diagnostics.session_logs),
        "log_files_created": [],
        "recommendations": []
    }
    
    # Check for log files
    for log_dir in LOG_DIRS:
        dir_path = os.path.join(LOGS_BASE, log_dir)
        if os.path.exists(dir_path):
            for file in os.listdir(dir_path):
                if file.endswith('.log'):
                    summary["log_files_created"].append(f"{log_dir}/{file}")
    
    # Add recommendations based on common issues
    summary["recommendations"] = [
        "Check outlook_debug/phases.log for Outlook configuration steps",
        "Review outlook_debug/protocols.log for protocol connection attempts", 
        "Examine outlook_debug/authentication.log for auth flow issues",
        "Check outlook_debug/errors.log for detailed error context"
    ]
    
    _write_json_line("diagnostics/debug_summary.log", summary)
    
    return json.dumps(summary, indent=2)