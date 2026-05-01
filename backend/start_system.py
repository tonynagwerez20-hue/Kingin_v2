"""
Hedge Trading System - Master Control
Acts as a Toggle: START or STOP the entire system.
"""
import subprocess
import sys
import time
import os
import json
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent
LOCK_FILE = PROJECT_ROOT / "system.lock"

def get_python_cmd():
    """Get the correct Python interpreter."""
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    
    venv_dot = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_dot.exists():
        return str(venv_dot)
        
    return sys.executable

def start_process(name, command, cwd=None, env=None):
    """Start a detached subprocess in a new console."""
    try:
        # Windows: CREATE_NEW_CONSOLE ensures it runs in a separate window
        # and persists after this script exits.
        creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        
        process = subprocess.Popen(
            command,
            cwd=cwd or PROJECT_ROOT,
            env=env or os.environ,
            creationflags=creation_flags
        )
        print(f"[OK] {name} launched (PID: {process.pid})")
        return process.pid
    except Exception as e:
        print(f"[FAIL] Failed to start {name}: {e}")
        return None

def stop_system():
    """Stop all running processes found in lock file."""
    print(f"\n{'='*60}")
    print("STOPPING SYSTEM...")
    print(f"{'='*60}")
    
    try:
        with open(LOCK_FILE, 'r') as f:
            data = json.load(f)
            
        pids = data.get("processes", {})
        
        for name, pid in pids.items():
            print(f"Stopping {name} (PID: {pid})...", end=" ")
            try:
                # Force kill on Windows
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                print("Killed.")
            except Exception as e:
                print(f"Error: {e}")
                
        # Remove lock file
        os.remove(LOCK_FILE)
        print("\n[SUCCESS] System Stopped and Lock File removed.")
        
    except FileNotFoundError:
        print("Lock file not found. System already stopped?")
    except Exception as e:
        print(f"Error stopping system: {e}")
        
    time.sleep(2) # Let user read output

def start_system():
    """Start all system components."""
    print(f"\n{'='*60}")
    print("STARTING SYSTEM...")
    print(f"{'='*60}")
    
    python_cmd = get_python_cmd()
    pids = {}
    
    # 1. Data Feed Server
    data_feed_path = PROJECT_ROOT / "data_feed" / "server.py"
    if data_feed_path.exists():
        pid = start_process("Data Feed Server", [python_cmd, str(data_feed_path)])
        if pid: pids["Data Feed Server"] = pid
    
    # 2. Trading Engine
    engine_path = PROJECT_ROOT / "Engine" / "main_loop.py"
    if engine_path.exists():
        # Add slight delay to let server bind port
        time.sleep(1) 
        pid = start_process("Trading Engine", [python_cmd, str(engine_path)])
        if pid: pids["Trading Engine"] = pid

    # 3. Dashboard (Modern React Terminal)
    react_dashboard_path = PROJECT_ROOT / "dashboard-react"
    if react_dashboard_path.exists():
        time.sleep(1)
        nodejs_dir = r"C:\Program Files\nodejs"
        npm_cmd = os.path.join(nodejs_dir, "npm.cmd")
        
        # v5.3 Secure Path: Prepend Node.js to PATH env for this process
        env = os.environ.copy()
        if os.path.exists(nodejs_dir):
            env["PATH"] = nodejs_dir + os.pathsep + env.get("PATH", "")
        else:
            npm_cmd = "npm" # Fallback
            
        pid = start_process("React Dashboard", [npm_cmd, "run", "dev"], cwd=str(react_dashboard_path), env=env)
        if pid: pids["React Dashboard"] = pid
        
    # Write Lock File
    if pids:
        try:
            with open(LOCK_FILE, 'w') as f:
                json.dump({"started": time.time(), "processes": pids}, f, indent=4)
            print(f"\n[SUCCESS] System Started. Lock file created.")
            print("You can close this window. The system will run in the background.")
            print("Run this script again to STOP the system.")
        except Exception as e:
            print(f"Failed to write lock file: {e}")
    else:
        print("No processes started.")

    time.sleep(3) # Let user read output

def main():
    if LOCK_FILE.exists():
        stop_system()
    else:
        start_system()

if __name__ == "__main__":
    main()
