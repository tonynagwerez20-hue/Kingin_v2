"""
Launch the local KingIn API and React dashboard for desktop/browser use.
"""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main():
    project_root = Path(__file__).parent.resolve()
    frontend_dir = project_root / "kingin-vite"
    api_script = project_root / "kingin_api.py"

    print("=== KingIn Dashboard - Auto Launch ===")

    if not api_script.exists():
        print(f"ERROR: API script not found at {api_script}")
        return 1

    if not (frontend_dir / "package.json").exists():
        print(f"ERROR: Dashboard package not found at {frontend_dir}")
        return 1

    print("[1/3] Starting KingIn API server...")
    api_process = subprocess.Popen([sys.executable, str(api_script)], cwd=str(project_root))
    print(f"   API PID: {api_process.pid}")

    time.sleep(3)

    print("[2/3] Starting React dashboard...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    dashboard_process = subprocess.Popen([npm_cmd, "run", "dev"], cwd=str(frontend_dir))
    print(f"   Dashboard PID: {dashboard_process.pid}")

    time.sleep(5)

    dashboard_url = "http://localhost:5000"
    print(f"[3/3] Opening {dashboard_url}")
    webbrowser.open(dashboard_url)

    print("\nDashboard launched.")
    print("Press Ctrl+C to stop both processes.")

    try:
        while True:
            if api_process.poll() is not None:
                print("API server stopped.")
                break
            if dashboard_process.poll() is not None:
                print("Dashboard server stopped.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for process in (dashboard_process, api_process):
            if process.poll() is None:
                process.terminate()
        for process in (dashboard_process, api_process):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
