#!/usr/bin/env python3
"""
Monitor SMTP logs in real-time
"""
import os
import time
import sys

def monitor_logs():
    """Monitor SMTP logs in real-time"""
    log_files = [
        "logs/internal_smtp.log",
        "logs/email_processing.log",
        "logs/smtp_connections.log",
        "logs/smtp_errors.log"
    ]
    
    print("🔍 Monitoring SMTP logs...")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    # Track file positions
    file_positions = {}
    for log_file in log_files:
        if os.path.exists(log_file):
            file_positions[log_file] = os.path.getsize(log_file)
        else:
            file_positions[log_file] = 0
    
    try:
        while True:
            for log_file in log_files:
                if os.path.exists(log_file):
                    current_size = os.path.getsize(log_file)
                    if current_size > file_positions[log_file]:
                        # New content available
                        with open(log_file, 'r') as f:
                            f.seek(file_positions[log_file])
                            new_content = f.read()
                            if new_content.strip():
                                print(f"\n📄 {log_file}:")
                                for line in new_content.strip().split('\n'):
                                    if line.strip():
                                        print(f"  {line}")
                        file_positions[log_file] = current_size
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")

if __name__ == "__main__":
    monitor_logs()
