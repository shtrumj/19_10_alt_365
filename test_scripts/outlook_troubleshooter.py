#!/usr/bin/env python3
"""
Automated Outlook Troubleshooting Tool
Analyzes connection patterns and provides specific recommendations
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import requests
from typing import Dict, List, Any, Optional

class OutlookTroubleshooter:
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = logs_dir
        self.issues = []
        self.recommendations = []
        
    def analyze_logs(self) -> Dict[str, Any]:
        """Analyze all relevant logs for Outlook issues"""
        print("🔍 Analyzing Outlook connection logs...")
        
        analysis = {
            "autodiscover_issues": self._analyze_autodiscover_logs(),
            "mapi_issues": self._analyze_mapi_logs(),
            "health_issues": self._analyze_health_logs(),
            "connection_patterns": self._analyze_connection_patterns(),
            "recommendations": []
        }
        
        # Generate recommendations based on analysis
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_autodiscover_logs(self) -> Dict[str, Any]:
        """Analyze Autodiscover logs for patterns"""
        autodiscover_file = os.path.join(self.logs_dir, "web", "autodiscover", "autodiscover.log")
        
        if not os.path.exists(autodiscover_file):
            return {"error": "Autodiscover log file not found"}
        
        requests_by_ip = defaultdict(list)
        user_agents = Counter()
        error_count = 0
        success_count = 0
        
        try:
            with open(autodiscover_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        
                        if log_entry.get("event") == "request":
                            details = log_entry.get("details", {})
                            ip = details.get("ip", "unknown")
                            ua = details.get("ua", "unknown")
                            
                            requests_by_ip[ip].append(log_entry)
                            user_agents[ua] += 1
                            
                        elif log_entry.get("event") == "response":
                            success_count += 1
                            
                    except json.JSONDecodeError:
                        error_count += 1
                        continue
        
        except Exception as e:
            return {"error": f"Failed to read autodiscover log: {e}"}
        
        # Detect loops (same IP making many requests)
        loops_detected = []
        for ip, requests in requests_by_ip.items():
            if len(requests) > 10:
                loops_detected.append({
                    "ip": ip,
                    "request_count": len(requests),
                    "user_agents": list(set([r.get("details", {}).get("ua", "") for r in requests]))
                })
        
        return {
            "total_requests": sum(len(reqs) for reqs in requests_by_ip.values()),
            "unique_ips": len(requests_by_ip),
            "user_agents": dict(user_agents.most_common(10)),
            "loops_detected": loops_detected,
            "success_rate": success_count / (success_count + error_count) if (success_count + error_count) > 0 else 0
        }
    
    def _analyze_mapi_logs(self) -> Dict[str, Any]:
        """Analyze MAPI logs for connection issues"""
        mapi_file = os.path.join(self.logs_dir, "web", "mapi", "mapi.log")
        
        if not os.path.exists(mapi_file):
            return {"error": "MAPI log file not found"}
        
        connect_attempts = 0
        connect_successes = 0
        auth_failures = 0
        request_errors = 0
        
        try:
            with open(mapi_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        event = log_entry.get("event", "")
                        
                        if event == "raw_request":
                            connect_attempts += 1
                        elif event == "connect_success":
                            connect_successes += 1
                        elif event == "auth_failed":
                            auth_failures += 1
                        elif "error" in event.lower():
                            request_errors += 1
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            return {"error": f"Failed to read MAPI log: {e}"}
        
        return {
            "connect_attempts": connect_attempts,
            "connect_successes": connect_successes,
            "auth_failures": auth_failures,
            "request_errors": request_errors,
            "success_rate": connect_successes / connect_attempts if connect_attempts > 0 else 0
        }
    
    def _analyze_health_logs(self) -> Dict[str, Any]:
        """Analyze health monitoring logs"""
        health_file = os.path.join(self.logs_dir, "outlook", "health_issues.log")
        
        if not os.path.exists(health_file):
            return {"no_issues": True}
        
        issues_by_type = Counter()
        issues_by_severity = Counter()
        recent_issues = []
        
        try:
            with open(health_file, 'r') as f:
                for line in f:
                    try:
                        issue = json.loads(line.strip())
                        issue_type = issue.get("issue_type", "unknown")
                        severity = issue.get("severity", "unknown")
                        timestamp = issue.get("timestamp", 0)
                        
                        issues_by_type[issue_type] += 1
                        issues_by_severity[severity] += 1
                        
                        # Keep recent issues (last 24 hours)
                        if timestamp > time.time() - 86400:
                            recent_issues.append(issue)
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            return {"error": f"Failed to read health log: {e}"}
        
        return {
            "issues_by_type": dict(issues_by_type),
            "issues_by_severity": dict(issues_by_severity),
            "recent_issues_count": len(recent_issues),
            "critical_issues": issues_by_severity.get("high", 0)
        }
    
    def _analyze_connection_patterns(self) -> Dict[str, Any]:
        """Analyze overall connection patterns"""
        # This would analyze patterns across all logs
        # For now, return a placeholder
        return {
            "outlook_2021_detected": True,
            "registry_fix_needed": True,
            "profile_recreation_recommended": False
        }
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate specific recommendations based on analysis"""
        recommendations = []
        
        # Check for Autodiscover loops
        autodiscover = analysis.get("autodiscover_issues", {})
        if autodiscover.get("loops_detected"):
            recommendations.append({
                "priority": "high",
                "category": "autodiscover",
                "issue": "Autodiscover loops detected",
                "description": "Outlook is making repeated Autodiscover requests without progressing",
                "solution": "Apply the Outlook 2021 registry fix to prevent O365 endpoint attempts",
                "action": "Download and apply outlook_2021_registry_fix.reg"
            })
        
        # Check MAPI connection success rate
        mapi = analysis.get("mapi_issues", {})
        if mapi.get("success_rate", 1) < 0.5:
            recommendations.append({
                "priority": "high",
                "category": "mapi",
                "issue": "Low MAPI connection success rate",
                "description": f"Only {mapi.get('success_rate', 0)*100:.1f}% of MAPI connections succeed",
                "solution": "Check authentication credentials and network connectivity",
                "action": "Verify username/password and test MAPI endpoint manually"
            })
        
        # Check for authentication failures
        if mapi.get("auth_failures", 0) > 0:
            recommendations.append({
                "priority": "medium",
                "category": "authentication",
                "issue": "Authentication failures detected",
                "description": f"{mapi.get('auth_failures')} authentication failures in MAPI logs",
                "solution": "Verify credentials and check for account lockouts",
                "action": "Reset password or check Active Directory status"
            })
        
        # Check for health issues
        health = analysis.get("health_issues", {})
        if health.get("critical_issues", 0) > 0:
            recommendations.append({
                "priority": "high",
                "category": "health",
                "issue": "Critical health issues detected",
                "description": f"{health.get('critical_issues')} critical issues in the last 24 hours",
                "solution": "Review health monitoring dashboard for specific issues",
                "action": "Check /owa/admin/outlook-health for detailed analysis"
            })
        
        # Always recommend registry fix for Outlook 2021
        recommendations.append({
            "priority": "medium",
            "category": "configuration",
            "issue": "Outlook 2021 optimization",
            "description": "Outlook Professional Plus 2021 requires specific registry settings",
            "solution": "Apply registry fix to disable O365 endpoint preference",
            "action": "Download and apply outlook_2021_registry_fix.reg, then restart Outlook"
        })
        
        return recommendations
    
    def test_connectivity(self, server_url: str = "https://owa.shtrum.com") -> Dict[str, Any]:
        """Test connectivity to Exchange server endpoints"""
        print(f"🧪 Testing connectivity to {server_url}...")
        
        results = {}
        
        # Test Autodiscover endpoints
        autodiscover_tests = [
            ("JSON Autodiscover", f"https://autodiscover.shtrum.com/autodiscover/autodiscover.json/v1.0/yonatan@shtrum.com"),
            ("XML Autodiscover", f"https://autodiscover.shtrum.com/autodiscover/autodiscover.xml"),
            ("MAPI Endpoint", f"{server_url}/mapi/emsmdb"),
            ("EWS Endpoint", f"{server_url}/EWS/Exchange.asmx"),
            ("OWA Endpoint", f"{server_url}/owa"),
            ("OAB Endpoint", f"{server_url}/oab/oab.xml")
        ]
        
        for name, url in autodiscover_tests:
            try:
                response = requests.get(url, timeout=10, verify=False)
                results[name] = {
                    "status": "success" if response.status_code < 400 else "error",
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def generate_report(self, analysis: Dict[str, Any], connectivity: Dict[str, Any]) -> str:
        """Generate a comprehensive troubleshooting report"""
        report = []
        report.append("=" * 80)
        report.append("OUTLOOK TROUBLESHOOTING REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Connectivity Results
        report.append("🌐 CONNECTIVITY TEST RESULTS:")
        report.append("-" * 40)
        for endpoint, result in connectivity.items():
            status = "✅" if result.get("status") == "success" else "❌"
            report.append(f"{status} {endpoint}: {result.get('status_code', 'N/A')}")
        report.append("")
        
        # Autodiscover Analysis
        autodiscover = analysis.get("autodiscover_issues", {})
        report.append("🔍 AUTODISCOVER ANALYSIS:")
        report.append("-" * 40)
        report.append(f"Total Requests: {autodiscover.get('total_requests', 0)}")
        report.append(f"Unique IPs: {autodiscover.get('unique_ips', 0)}")
        report.append(f"Success Rate: {autodiscover.get('success_rate', 0)*100:.1f}%")
        
        loops = autodiscover.get("loops_detected", [])
        if loops:
            report.append(f"⚠️  Loops Detected: {len(loops)} clients in Autodiscover loops")
            for loop in loops[:3]:  # Show first 3
                report.append(f"   - IP {loop['ip']}: {loop['request_count']} requests")
        report.append("")
        
        # MAPI Analysis
        mapi = analysis.get("mapi_issues", {})
        report.append("🔌 MAPI CONNECTION ANALYSIS:")
        report.append("-" * 40)
        report.append(f"Connection Attempts: {mapi.get('connect_attempts', 0)}")
        report.append(f"Successful Connections: {mapi.get('connect_successes', 0)}")
        report.append(f"Authentication Failures: {mapi.get('auth_failures', 0)}")
        report.append(f"Success Rate: {mapi.get('success_rate', 0)*100:.1f}%")
        report.append("")
        
        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            report.append("💡 RECOMMENDATIONS:")
            report.append("-" * 40)
            for i, rec in enumerate(recommendations, 1):
                priority = rec.get("priority", "medium").upper()
                report.append(f"{i}. [{priority}] {rec.get('issue', 'Unknown issue')}")
                report.append(f"   Solution: {rec.get('solution', 'No solution provided')}")
                report.append(f"   Action: {rec.get('action', 'No action specified')}")
                report.append("")
        
        # Health Issues
        health = analysis.get("health_issues", {})
        if not health.get("no_issues", False):
            report.append("🏥 HEALTH MONITORING:")
            report.append("-" * 40)
            report.append(f"Recent Issues: {health.get('recent_issues_count', 0)}")
            report.append(f"Critical Issues: {health.get('critical_issues', 0)}")
            
            issues_by_type = health.get("issues_by_type", {})
            if issues_by_type:
                report.append("Issue Types:")
                for issue_type, count in issues_by_type.items():
                    report.append(f"   - {issue_type}: {count}")
        
        report.append("")
        report.append("=" * 80)
        report.append("For detailed analysis, visit: https://owa.shtrum.com/owa/admin/outlook-health")
        report.append("=" * 80)
        
        return "\n".join(report)

def main():
    """Main troubleshooting function"""
    print("🔧 Outlook Professional Plus 2021 Troubleshooter")
    print("=" * 60)
    
    # Change to project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    troubleshooter = OutlookTroubleshooter()
    
    # Run analysis
    analysis = troubleshooter.analyze_logs()
    connectivity = troubleshooter.test_connectivity()
    
    # Generate and display report
    report = troubleshooter.generate_report(analysis, connectivity)
    print(report)
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"outlook_troubleshooting_report_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Report saved to: {report_file}")
    print("🎯 Next steps:")
    print("1. Apply the registry fix: outlook_2021_registry_fix.reg")
    print("2. Create a new Outlook profile")
    print("3. Monitor the health dashboard: /owa/admin/outlook-health")

if __name__ == "__main__":
    main()
