# Desktop App Changes (summary)

Date: 2026-04-15

This file documents the minimal, safe changes made to improve portability, robustness, and developer ergonomics for the Tauri + Engine desktop app.

Summary of key edits
- `BUILD_DESKTOP_APP.bat`: corrected npm script to `npm run tauri:build` (matches `package.json`).
- `create_shortcut.bat`: now uses repository icon at `src-tauri\icons\icon.ico` when available and falls back to the built exe icon.
- Removed legacy `CreateShortcut.vbs` (contained hardcoded, user-specific paths).
- `START_ALL.bat`: replaced hardcoded Lenovo Python path with robust detection:
  - Prefer `ITS_PYTHON_EXE` environment variable if set
  - Try `where python` and `where py` on PATH
  - Fallback to `python` so portable setups work
- `src-tauri/src/lib.rs`: hardened Python detection logic used by Tauri backend — now prefers `ITS_PYTHON_EXE`, inspects PATH, and checks for the Windows py launcher. Removed machine-specific fallback paths.
- `src/Dashboard.jsx`: fixed timestamp parsing so the UI correctly interprets ISO8601 timestamps emitted by the engine and shows `LIVE` when current.

Other repo hygiene
- Added/updated `.gitignore` entries (build artifacts, virtualenvs, runtime exports such as `engine_state.json`).
- Deleted corrupted runtime `engine_state.json` (engine will create a fresh one).

Why these changes
- The repository had multiple absolute paths (`C:\Users\LENOVO\...`) and checked-in build artifacts which made the project non-portable and caused silent failures on other machines.
- Tauri backend and the React dashboard expected different timestamp formats; the dashboard would show OFFLINE when the engine actually wrote fresh ISO timestamps.

What I DID NOT change (intentional)
- I did not refactor the engine internals or ML model behavior.
- I did not remove or change essential configuration files such as `config/trading_params_lite.json`.

How to test locally (quick smoke test)
1. Ensure you have Python 3.10+ and Node 18+ installed, and `git` configured.
2. From repo root run (PowerShell):

```powershell
npm ci
npm run dev  # optional: run the frontend dev server
npm run tauri:dev  # run the Tauri dev app (requires Rust toolchain + tauri prerequisites)
```

3. From the running Tauri app: open the Login page and try demo login. `mt5_auth.py` will return demo mode if MetaTrader5 is not installed.
4. Start the engine from the Tauri UI `START ENGINE` button (or run `START_ALL.bat`). The dashboard should show `LIVE` once `engine_state.json` is updated.

Environment variables and recommended setup
- Optionally set `ITS_PYTHON_EXE` to the full Python executable path to control which Python is used by the Tauri backend and the start scripts.
- Ensure `pyzmq` and other Python dependencies from `requirements.txt` are installed in the Python environment used by the engine.

Next recommended steps (optional)
- Add a lightweight `validate_env` script to confirm Python packages and the MT5 environment.
- Remove large generated artifacts from Git history (if desired) using `git filter-repo` or similar — this is optional and destructive to history.

If anything here is unexpected, tell me and I will revert or adjust specific edits.

-- changes authored by automated assistant (pair-programming) — review before publishing
