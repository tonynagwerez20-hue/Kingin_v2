"""
Auto-launch script for the Hedge Trading System Dashboard.
This script starts the FastAPI server and automatically opens the React dashboard in the default browser.
"""
import subprocess
import time
import webbrowser
import sys
from pathlib import Path

def main():
    print("=== Hedge Trading System - Auto Launch ===")
    
    # Get project root
    project_root = Path(__file__).parent
    
    # Start FastAPI server
    print("[1/3] Starting FastAPI server...")
    server_script = project_root / "data_feed" / "server.py"
    
    if not server_script.exists():
        print(f"ERROR: Server script not found at {server_script}")
        return
    
    # Start server in background
    server_process = subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print(f"   Server PID: {server_process.pid}")
    
    # Wait for server to start
    print("[2/3] Waiting for server to initialize...")
    time.sleep(5)
    
    # Start dashboard server (simple HTTP server for static files)
    print("[3/3] Starting dashboard server...")
    dashboard_path = project_root / "dashboard-react"
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", "3000"],
        cwd=str(dashboard_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"   Dashboard server PID: {dashboard_process.pid}")
    
    # Wait a moment for the dashboard server to start
    time.sleep(2)
    
    # Try to open the dashboard URL
    dashboard_url = "http://localhost:3000"
    
    print(f"   Opening {dashboard_url} in default browser...")
    webbrowser.open(dashboard_url)
    
    print("\n✓ Dashboard launched successfully!")
    print(f"   Dashboard URL: {dashboard_url}")
    print(f"   API Server: http://localhost:8000")
    print("\nPress Ctrl+C to stop the server...")
    
    try:
        # Keep script running
        server_process.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        server_process.terminate()
        dashboard_process.terminate()
        server_process.wait()
        dashboard_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    main()
