
import subprocess
import time
import sys
import os
import argparse
import signal
from pathlib import Path

# Paths
CWD = Path(__file__).parent
PYTHON = sys.executable 

def run_server(mode="DTC"):
    print(f"[Backtest] Starting Data Feed Server in {mode} mode...", flush=True)
    env = os.environ.copy()
    env["DATA_SOURCE_TYPE"] = mode
    
    # Start server as a subprocess
    # Use -u for unbuffered output
    server_proc = subprocess.Popen([PYTHON, "-u", "data_feed/server.py"], cwd=CWD, env=env)
    return server_proc

def run_strategy():
    print("[Backtest] Starting Strategy Loop in BACKTEST mode...", flush=True)
    # Start strategy in the foreground so we can see logs
    # We use --backtest flag to trigger the logic in main_loop.py
    try:
        subprocess.run([PYTHON, "-u", "Engine/main_loop.py", "--backtest"], cwd=CWD)
    except KeyboardInterrupt:
        print("\n[Backtest] Shutdown requested...", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Run System Validation / Backtest")
    parser.add_argument("--mode", choices=["DTC", "CSV"], default="DTC", help="Replay Mode (DTC=Sierra Chart, CSV=Local Files)")
    args = parser.parse_args()

    print("="*60, flush=True)
    print(f"   SYSTEM BACKTEST RUNNER (${args.mode} Mode)", flush=True)
    print("="*60, flush=True)
    
    if args.mode == "DTC":
        print("INSTRUCTIONS FOR DTC REPLAY:", flush=True)
        print("1. Open Sierra Chart.", flush=True)
        print("2. Go to 'Trade' -> 'Trade Simulation Mode On'.", flush=True)
        print("3. Open a Chart for XAUUSD (or target symbol).", flush=True)
        print("4. Go to 'Edit' -> 'Replay Chart'.", flush=True)
        print("5. Set your Speed and Start Time, then press Play.", flush=True)
        print("6. Ensure DTC Server is enabled in Sierra Chart (Global Settings -> tool config).", flush=True)
        print("-" * 60, flush=True)
        print("Waiting 5 seconds for you to read this...", flush=True)
        time.sleep(5)

    server_proc = None
    try:
        # 1. Start Server
        server_proc = run_server(mode=args.mode)
        
        # 2. Wait for server (5s)
        print("[Backtest] Waiting 5s for server to initialize...", flush=True)
        time.sleep(5)
        
        # 3. Start Strategy
        run_strategy()
        
    except Exception as e:
        print(f"[Backtest] CRITICAL ERROR: {e}")
    finally:
        if server_proc:
            print("[Backtest] Cleaning up server process...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                 server_proc.kill()
            
        print("[Backtest] Test Complete.")

if __name__ == "__main__":
    main()
