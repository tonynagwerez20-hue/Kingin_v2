import socket
import time
import os
import sys
from pathlib import Path

def check_port(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def check_file_age(filepath, max_age=300):
    path = Path(filepath)
    if not path.exists():
        print(f"[FAIL] File not found: {filepath}")
        return False
        
    mtime = path.stat().st_mtime
    age = time.time() - mtime
    
    if age > max_age:
        print(f"[WARN] File is stale: {filepath} ({age:.0f}s old)")
        return False
    else:
        print(f"[OK] File is fresh: {filepath} ({age:.0f}s old)")
        return True

def main():
    print("=== Data Feed Diagnostic Tool ===")
    
    # 1. Check Files
    print("\n1. Checking Sierra Export Files...")
    files = [
        "data_feed/sierra_H1.txt",
        "data_feed/sierra_M15.txt",
        "data_feed/sierra_M5.txt"
    ]
    
    all_files_ok = True
    for f in files:
        if not check_file_age(f):
            all_files_ok = False
            
    if all_files_ok:
        print("-> All data files are updating correctly.")
    else:
        print("-> ALERT: Some files are not updating. Check Sierra Chart.")

    # 2. Check Server Port
    print("\n2. Checking Data Feed Server (Port 8000)...")
    if check_port("localhost", 8000):
        print("[OK] Port 8000 is open (Server accepting connections)")
    else:
        print("[FAIL] Port 8000 is CLOSED. Server is NOT running.")
        print("   -> Suggested Action: Restart the system or check logs.")

    # 3. Check API
    print("\n3. Testing API Response...")
    try:
        import urllib.request
        import json
        
        with urllib.request.urlopen("http://localhost:8000/ohlc?tf=M5&limit=1") as response:
            if response.getcode() == 200:
                data = json.loads(response.read())
                print(f"[OK] API returned data: {json.dumps(data, indent=2)}")
            else:
                print(f"[FAIL] API error code: {response.getcode()}")
    except Exception as e:
        print(f"[FAIL] API connection failed: {e}")

if __name__ == "__main__":
    main()
