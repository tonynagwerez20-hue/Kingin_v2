# Institutional Trading System — Final Report

Date: 2026-04-15

Purpose
- Ensure the Tauri desktop wrapper and trading engine are portable, robust, and testable on a Windows machine.

What I changed (summary)
- Made Python detection portable: `START_ALL.bat` and `src-tauri/src/lib.rs` now prefer `ITS_PYTHON_EXE` env var and fallback to PATH (`python`, `py`).
- Fixed build script invocation in `BUILD_DESKTOP_APP.bat` to use `npm run tauri:build`.
- Made desktop shortcut creation robust: `create_shortcut.bat` uses `src-tauri\icons\icon.ico` when available and removes hardcoded VBS usage.
- Hardened `read_engine_state()` in `src-tauri/src/lib.rs` to search multiple locations and validate JSON.
- Fixed frontend timestamp parsing in `src/Dashboard.jsx` so ISO timestamps from engine produce a `LIVE` status.
- Added `scripts/validate_env.py` (env checker) and `scripts/update_engine_state.py` (test helper to refresh `engine_state.json`).
- Removed problematic reserved file `nul` and preserved its content in `nul_escaped.txt`.
- Added `DESKTOP_APP_CHANGES.md` (change log) and this final report.
- Committed and pushed the changes to `master` on your GitHub repository.

Quick verification (what I ran)
1. `python scripts/validate_env.py` — confirmed Python, Node, npm, Rust available. (pyzmq / MetaTrader5 optional)
2. Started dev frontend: `npm run dev` (Vite at http://localhost:1420).
3. Started Tauri dev: `npm run tauri:dev` (launched native wrapper in dev mode).
4. Started engine: `cmd /c START_ALL.bat` — launched data server and engine in background (demo flow when MT5 not available).
5. Used `python state_exporter.py` and `python scripts/update_engine_state.py` to generate/refresh `engine_state.json` and include `ml_filter` sample.
6. Verified `engine_state.json` is valid JSON and served by the frontend; Dashboard should show LIVE and display ML panel.

How to run the full system (developer machine)
1. Install prerequisites: Node 18+, npm, Python 3.10+, Rust toolchain (for Tauri build).
2. (optional) Set `ITS_PYTHON_EXE` to the full path of the Python executable you want the app to use.
   - Windows PowerShell: `setx ITS_PYTHON_EXE "C:\Path\to\python.exe"`
3. Install JS deps:

```powershell
npm ci
```

4. Start frontend + Tauri (dev):

```powershell
npm run dev       # starts vite on http://localhost:1420
npm run tauri:dev # opens Tauri dev window (connects to vite)
```

5. Start engine (background):

```powershell
# either from PowerShell
cmd /c START_ALL.bat
# or run the engine Python directly (with preferred python)
"%ITS_PYTHON_EXE%" -m Engine.modular_bootstrapper
```

6. Open the app in the Tauri window or the browser (http://localhost:1420). Login (use demo mode if MT5 not installed). Dashboard panels should update.

Packaging / Desktop installer notes
- Run `npm run build` then `npm run tauri:build` (or use `BUILD_DESKTOP_APP.bat`) to produce a Windows installer/bundle.
- `create_shortcut.bat` creates desktop shortcuts pointing at `src-tauri\target\release\institutional-trading-system.exe` or falls back to repo icon. Adjust if you install to a different path.

Portability checklist
- Prefer `ITS_PYTHON_EXE` env var for deterministic Python selection.
- Ensure `pyzmq` and engine Python deps are installed in the Python environment used by the app if using live MT5/ZMQ bridging.
- Keep `models/lgbm_signal_filter.json` with your trained model if ML filtering is required.
- Avoid committing large build artifacts; consider removing `src-tauri/target/` from history if you want a smaller repo.

Next recommended tasks (optional)
- Add CI job to run `scripts/validate_env.py` on PRs.
- Create automated UI tests (Playwright) that exercise the login -> start engine -> dashboard flow.
- Create an installer post-build step to create shortcuts and register icons (Wix/NSIS; current Tauri bundlers may include these options).

Contact & follow-up
- I updated and pushed changes to your GitHub repository. If you want, I can create the Playwright test harness and run it here (requires installing Playwright). Otherwise, I can guide you through running a manual test or run the test if you approve installing the extra packages.

-- end of final report
