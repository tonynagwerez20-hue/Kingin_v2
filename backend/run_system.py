
import subprocess
import time
import sys
import os
import threading
from pathlib import Path

# Paths
CWD = Path(__file__).parent
PYTHON = sys.executable # Use the current interpreter (likely the .venv one)

def run_server():
    print("[Launcher] Starting Data Feed Server (server.py)...")
    # Start server as a subprocess
    server_proc = subprocess.Popen([PYTHON, "data_feed/server.py"], cwd=CWD)
    return server_proc

def run_strategy():
    print("[Launcher] Starting Strategy Loop (main_loop.py)...")
    # Start strategy in the foreground so we can see logs
    try:
        subprocess.run([PYTHON, "Engine/main_loop.py"], cwd=CWD)
    except KeyboardInterrupt:
        print("\n[Launcher] Shutdown requested...")

def main():
    print("==========================================")
    print("   IGOF SYSTEM CONSOLIDATED LAUNCHER  ")
    print("==========================================")
    
    server_proc = None
    try:
        # 1. Start Server
        server_proc = run_server()
        
        # 2. Wait for server (5s)
        print("[Launcher] Waiting 5s for server to bind to port 8000...")
        time.sleep(5)
        
        # 3. Start Strategy
        run_strategy()
        
    except Exception as e:
        print(f"[Launcher] CRITICAL ERROR: {e}")
    finally:
        if server_proc:
            print("[Launcher] Cleaning up server process...")
            server_proc.terminate()
            server_proc.wait()
        print("[Launcher] System exited.")

if __name__ == "__main__":
    main()
