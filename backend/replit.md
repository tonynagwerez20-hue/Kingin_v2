# KingIn Institutional Trading System

## Overview
A professional trading control room dashboard (KingIn) with a Python-based trading engine (MT5 integration). The frontend is a Vite + React app displaying real-time trading data, connected to a Python API server.

## Project Structure

```
kingin-vite/          ← Main web app (Vite + React, runs in browser)
  src/
    App.jsx           - App shell, handles auth state
    KingInDashboard.jsx - Main dashboard UI (8 panels)
    Dashboard.jsx     - Alternative dashboard view
    Login.jsx         - Login page
    tauri-stub.js     - HTTP bridge: maps Tauri invoke() to real API calls
    hooks/            - useWebSocket, useAppStore
    lib/              - formatters, mockData
    store/            - Zustand app state
  vite.config.js      - Dev server config; proxies /api/* → localhost-only API on port 8080

kingin_api.py         ← KingIn Dashboard API Server (port 8080)
  GET  /engine/state  - Live engine state (balance, equity, positions, signals)
  POST /engine/start  - Start Engine/main_loop.py subprocess
  POST /engine/stop   - Stop the engine subprocess
  POST /engine/init   - Health check / initialization
  POST /engine/auth   - Auth handshake

dashboard-react/      ← Legacy Next.js app (not currently served)

Engine/               ← Python trading engine
supervisor.py         ← System supervisor
support/              ← Supporting Python modules
data_feed/            ← Market data feed (FastAPI on port 8000)
data/hedge.db         ← SQLite: account state and trade records
storage/logs/         ← Audit logs written by the engine
```

## Running the App
Two workflows run in parallel:
1. **Start application** — `cd kingin-vite && npm run dev` (port 5000, Replit webview)
2. **KingIn API** — `python kingin_api.py` (port 8080, console)

The Vite proxy routes `/api/*` requests to the API server, so the frontend never makes cross-origin calls.

## Key Notes
- Originally a Tauri desktop app; adapted for web by replacing `@tauri-apps/api/tauri` with `src/tauri-stub.js`
- `tauri-stub.js` now makes real relative `/api` HTTP calls to the KingIn API server (not mock data)
- Backend control tokens are not exposed to browser JavaScript; the local Vite proxy strips incoming control-token headers and injects the server-side token for engine start/stop requests
- `master` contains local Windows desktop/browser scripts, not a complete Tauri native desktop app project
- The API server reads live data from `data/hedge.db` (MT5 balance/trades) and `storage/logs/audit.json` (signals)
- When no MT5 connection exists, the dashboard falls back gracefully to illustrative mock data
- Auto-logs in with a demo session token (login auth is a separate planned task)
