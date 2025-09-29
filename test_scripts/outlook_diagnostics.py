#!/usr/bin/env python3
"""
Outlook Connection Diagnostics Tool

This script analyzes logs and provides detailed diagnostics for
Outlook auto-configuration issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import json
import glob
from datetime import datetime, timedelta
from collections import defaultdict
import re

LOGS_DIR = "logs"

class OutlookDiagnosticAnalyzer:
    def __init__(self):
        self.issues = []
        self.recommendations = []
        self.timeline = []
        
    def analyze_logs(self):
        """Analyze all relevant log files"""
        print("🔍 ANALYZING OUTLOOK CONNECTION LOGS...")
        print("=" * 60)
        
        # Analyze different log categories
        self.analyze_autodiscover_logs()
        self.analyze_mapi_logs() 
        self.analyze_ews_logs()
        self.analyze_authentication_patterns()
        self.detect_common_issues()
        
        return self.generate_report()
    
    def analyze_autodiscover_logs(self):
        """Analyze autodiscover logs"""
        print("\n📋 AUTODISCOVER ANALYSIS:")
        
        autodiscover_files = glob.glob(f"{LOGS_DIR}/web/autodiscover/*.log")
        json_requests = 0
        xml_requests = 0
        errors = 0
        recent_requests = []
        
        for log_file in autodiscover_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # Count request types
                            if log_entry.get("event") == "json_request":
                                json_requests += 1
                                recent_requests.append({
                                    "time": log_entry.get("ts"),
                                    "type": "JSON",
                                    "email": log_entry.get("details", {}).get("email"),
                                    "ua": log_entry.get("details", {}).get("ua", "")
                                })
                            elif log_entry.get("event") == "request":
                                xml_requests += 1
                                recent_requests.append({
                                    "time": log_entry.get("ts"),
                                    "type": "XML",
                                    "ua": log_entry.get("details", {}).get("ua", "")
                                })
                            elif "error" in log_entry.get("event", "").lower():
                                errors += 1
                                
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                continue
        
        # Sort by time and get recent requests
        recent_requests.sort(key=lambda x: x.get("time", ""), reverse=True)
        
        print(f"  📊 JSON Autodiscover Requests: {json_requests}")
        print(f"  📊 XML Autodiscover Requests: {xml_requests}")
        print(f"  ❌ Autodiscover Errors: {errors}")
        
        if recent_requests:
            print(f"  🕒 Most Recent Requests ({len(recent_requests[:5])} shown):")
            for req in recent_requests[:5]:
                time_str = req.get("time", "unknown")[:19] if req.get("time") else "unknown"
                ua_short = req.get("ua", "")[:50] + "..." if len(req.get("ua", "")) > 50 else req.get("ua", "")
                print(f"    • {time_str} | {req['type']} | {ua_short}")
        
        # Check for issues
        if json_requests == 0 and xml_requests == 0:
            self.issues.append("No autodiscover requests found - Outlook may not be reaching the server")
        elif json_requests == 0:
            self.issues.append("No JSON autodiscover requests - Modern Outlook clients may have issues")
        elif errors > 0:
            self.issues.append(f"Autodiscover errors detected: {errors}")
    
    def analyze_mapi_logs(self):
        """Analyze MAPI/HTTP logs"""
        print("\n🔌 MAPI/HTTP ANALYSIS:")
        
        mapi_files = glob.glob(f"{LOGS_DIR}/web/mapi/*.log")
        connect_attempts = 0
        successful_connects = 0
        auth_challenges = 0
        auth_received = 0
        parse_errors = 0
        sessions = set()
        
        for log_file in mapi_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            event = log_entry.get("event", "")
                            
                            if event == "connect_success":
                                successful_connects += 1
                                session = log_entry.get("session")
                                if session:
                                    sessions.add(session)
                            elif event == "auth_challenge":
                                auth_challenges += 1
                            elif event == "auth_received":
                                auth_received += 1
                            elif event == "parse_error":
                                parse_errors += 1
                            elif event == "emsmdb":
                                connect_attempts += 1
                                
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                continue
        
        print(f"  📊 MAPI Connection Attempts: {connect_attempts}")
        print(f"  ✅ Successful MAPI Connects: {successful_connects}")
        print(f"  🔐 Authentication Challenges: {auth_challenges}")
        print(f"  🔑 Authentication Received: {auth_received}")
        print(f"  🔧 Active Sessions: {len(sessions)}")
        print(f"  ❌ Parse Errors: {parse_errors}")
        
        # Check for issues
        if connect_attempts == 0:
            self.issues.append("No MAPI connection attempts - Outlook is not trying to connect via MAPI/HTTP")
        elif successful_connects == 0:
            self.issues.append("MAPI connections failing - Authentication or protocol issues")
        elif parse_errors > successful_connects:
            self.issues.append("High number of MAPI parse errors - Protocol compatibility issues")
        elif auth_challenges > 0 and auth_received == 0:
            self.issues.append("MAPI authentication challenges sent but no credentials received")
    
    def analyze_ews_logs(self):
        """Analyze EWS logs"""
        print("\n🌐 EWS ANALYSIS:")
        
        ews_files = glob.glob(f"{LOGS_DIR}/web/ews/*.log")
        ews_requests = 0
        finditem_requests = 0
        errors = 0
        
        for log_file in ews_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            event = log_entry.get("event", "")
                            
                            if event == "request":
                                ews_requests += 1
                            elif event == "finditem_response":
                                finditem_requests += 1
                            elif "error" in event.lower():
                                errors += 1
                                
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                continue
        
        print(f"  📊 EWS Requests: {ews_requests}")
        print(f"  📧 FindItem Responses: {finditem_requests}")
        print(f"  ❌ EWS Errors: {errors}")
        
        if ews_requests > 0:
            print("  ✅ EWS is being accessed by clients")
        else:
            print("  ⚠️  No EWS requests detected")
    
    def analyze_authentication_patterns(self):
        """Analyze authentication patterns"""
        print("\n🔐 AUTHENTICATION ANALYSIS:")
        
        auth_methods = defaultdict(int)
        failed_auths = 0
        
        # Check MAPI logs for auth patterns
        mapi_files = glob.glob(f"{LOGS_DIR}/web/mapi/*.log")
        for log_file in mapi_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            event = log_entry.get("event", "")
                            
                            if event == "auth_received":
                                auth_type = log_entry.get("auth_type", "unknown")
                                auth_methods[auth_type] += 1
                            elif event == "auth_challenge":
                                auth_methods["challenges_sent"] += 1
                                
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                continue
        
        print("  📊 Authentication Methods Seen:")
        for method, count in auth_methods.items():
            print(f"    • {method}: {count}")
        
        # Check for authentication issues
        if auth_methods.get("challenges_sent", 0) > 0 and sum(auth_methods.values()) == auth_methods.get("challenges_sent", 0):
            self.issues.append("Authentication challenges sent but no responses received")
        
        if "NTLM" in auth_methods and "Basic" in auth_methods:
            print("  ✅ Both NTLM and Basic authentication detected")
        elif "Basic" in auth_methods:
            print("  ⚠️  Only Basic authentication detected - NTLM may not be working")
    
    def detect_common_issues(self):
        """Detect common Outlook connection issues"""
        print("\n🔍 COMMON ISSUE DETECTION:")
        
        # Check for SSL/TLS issues
        if self._check_ssl_issues():
            self.issues.append("SSL/TLS certificate issues detected")
        
        # Check for protocol compatibility
        if self._check_protocol_compatibility():
            self.issues.append("Protocol compatibility issues detected")
        
        # Check for timeout patterns
        if self._check_timeout_patterns():
            self.issues.append("Connection timeout patterns detected")
    
    def _check_ssl_issues(self):
        """Check for SSL-related issues"""
        # This would check for SSL handshake failures, certificate errors, etc.
        # For now, we'll check if we see encrypted connection errors in logs
        return False  # Placeholder
    
    def _check_protocol_compatibility(self):
        """Check for protocol compatibility issues"""
        # Check if we have successful autodiscover but failed MAPI connections
        mapi_files = glob.glob(f"{LOGS_DIR}/web/mapi/*.log")
        autodiscover_files = glob.glob(f"{LOGS_DIR}/web/autodiscover/*.log")
        
        has_autodiscover = len(autodiscover_files) > 0
        has_mapi_errors = False
        
        for log_file in mapi_files:
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                    if "parse_error" in content or "Request too short" in content:
                        has_mapi_errors = True
                        break
            except FileNotFoundError:
                continue
        
        return has_autodiscover and has_mapi_errors
    
    def _check_timeout_patterns(self):
        """Check for timeout patterns"""
        # This would check for repeated requests with no responses
        return False  # Placeholder
    
    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n" + "=" * 60)
        print("🎯 OUTLOOK CONNECTION DIAGNOSTIC REPORT")
        print("=" * 60)
        
        if not self.issues:
            print("✅ No major issues detected!")
            print("\n📋 STATUS SUMMARY:")
            print("  • Autodiscover appears to be working")
            print("  • MAPI/HTTP connections are successful")
            print("  • Authentication is functioning")
            print("\n💡 POSSIBLE CAUSES OF 'STUCK' BEHAVIOR:")
            print("  • Outlook may be performing extended validation")
            print("  • Certificate trust issues (self-signed certificates)")
            print("  • Outlook cache from previous failed attempts")
            print("  • Network connectivity or firewall issues")
            print("  • Outlook waiting for additional server responses")
        else:
            print("❌ ISSUES DETECTED:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        
        print("\n🔧 RECOMMENDATIONS:")
        recommendations = [
            "Clear Outlook profile cache and recreate the account",
            "Verify SSL certificate is trusted (add to Windows certificate store)",
            "Check Windows Event Viewer for Outlook-specific errors",
            "Try configuring with manual server settings instead of auto-discovery",
            "Test with a different Outlook client or version",
            "Enable Outlook logging (HKEY_CURRENT_USER\\Software\\Microsoft\\Office\\16.0\\Outlook\\Options\\Mail\\EnableLogging=1)",
            "Check firewall/antivirus isn't blocking connections",
            "Verify DNS resolution for autodiscover.domain.com and owa.domain.com"
        ]
        
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
        
        print(f"\n📊 LOG FILES ANALYZED:")
        log_files = []
        for pattern in ["web/autodiscover/*.log", "web/mapi/*.log", "web/ews/*.log"]:
            log_files.extend(glob.glob(f"{LOGS_DIR}/{pattern}"))
        
        for log_file in log_files:
            try:
                size = os.path.getsize(log_file)
                print(f"  • {log_file} ({size} bytes)")
            except:
                print(f"  • {log_file} (not accessible)")
        
        return {
            "issues_found": len(self.issues),
            "issues": self.issues,
            "recommendations": recommendations,
            "log_files_analyzed": len(log_files)
        }

def main():
    """Run Outlook diagnostics"""
    analyzer = OutlookDiagnosticAnalyzer()
    result = analyzer.analyze_logs()
    
    # Also create a summary file
    with open("outlook_diagnostic_report.json", "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "analysis_result": result
        }, f, indent=2)
    
    print(f"\n💾 Full report saved to: outlook_diagnostic_report.json")
    
    return 0 if result["issues_found"] == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
