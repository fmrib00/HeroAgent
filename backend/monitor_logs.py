#!/usr/bin/env python3
"""
Simple log monitor for the backend
"""
import os
import time
from pathlib import Path

def monitor_logs():
    log_dir = Path("logs")
    if not log_dir.exists():
        print("No logs directory found")
        return
    
    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print("No log files found")
        return
    
    print(f"Monitoring {len(log_files)} log files...")
    print("Press Ctrl+C to stop")
    
    # Get the latest log file
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
    print(f"Monitoring: {latest_log}")
    
    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            # Go to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped monitoring")

if __name__ == "__main__":
    monitor_logs() 