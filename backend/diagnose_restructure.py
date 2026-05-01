import os
import sys
import json
from pathlib import Path
import subprocess
import time

def diagnose():
    print("=== KingIn Restructure Diagnostic ===")
    root = Path(__file__).parent.parent
    backend = root / "backend"
    frontend = root / "frontend"

    print(f"Root: {root}")
    print(f"Backend: {backend} ({'EXISTS' if backend.exists() else 'MISSING'})")
    print(f"Frontend: {frontend} ({'EXISTS' if frontend.exists() else 'MISSING'})")

    # 1. Backend Checks
    print("\n--- Backend Checks ---")
    critical_files = [
        "kingin_api.py",
        "Engine/main_loop.py",
        "config/trading_params_lite.json",
        ".env"
    ]
    for f in critical_files:
        path = backend / f
        print(f"File {f}: {'OK' if path.exists() else 'MISSING'}")

    # 2. Frontend Checks
    print("\n--- Frontend Checks ---")
    frontend_files = [
        "package.json",
        "vite.config.js",
        "electron/main.js",
        "src/api.js"
    ]
    for f in frontend_files:
        path = frontend / f
        print(f"File {f}: {'OK' if path.exists() else 'MISSING'}")

    # 3. Import Test
    print("\n--- Import Test ---")
    try:
        os.chdir(backend)
        sys.path.append(str(backend))
        import kingin_api
        print("Import kingin_api: SUCCESS")
    except Exception as e:
        print(f"Import kingin_api: FAILED ({e})")

    # 4. Port Check (is anything on 8088?)
    print("\n--- Port Check ---")
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        in_use = s.connect_ex(('127.0.0.1', 8088)) == 0
        print(f"Port 8088 in use: {in_use}")

    print("\nDiagnostic Complete.")

if __name__ == "__main__":
    diagnose()
