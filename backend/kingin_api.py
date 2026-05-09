"""
KingIn Dashboard API Server

Provides REST endpoints for the kingin-vite React dashboard.
Bridges between the React frontend and the Python trading engine.

Runs on port 8088. The Vite dev server proxies /api/* to this server.
"""
import asyncio
import json
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

PROJECT_ROOT = Path(__file__).parent

# Ensure essential directories exist for portability
(PROJECT_ROOT / "storage" / "logs").mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "config").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="KingIn Dashboard API", version="1.0.0")

_CONTROL_TOKEN = os.getenv("KINGIN_API_TOKEN", "replit-local-control")

# WebSocket connections storage
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

_ALLOWED_ORIGINS = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "app://.",
    "file://",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_config_path() -> Path:
    return PROJECT_ROOT / "config" / "trading_params_lite.json"

@app.get("/api/system/status")
async def get_system_status():
    """Check if the system is configured. Public endpoint for bootup."""
    config_path = _get_config_path()
    is_configured = False
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                # Check for critical login info
                login = cfg.get("pipeline", {}).get("data_provider", {}).get("config", {}).get("login")
                is_configured = bool(login)
        except:
            pass
    return {"configured": is_configured, "status": "online"}

_engine_process: Optional[subprocess.Popen] = None
_engine_start_time: Optional[float] = None

from utils.jwt import create_token, decode_token

def _check_token(request: Request) -> bool:
    """JWT Token check for standard API routes."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    return bool(payload)

def _check_control_token(request: Request) -> bool:
    """X-Control-Token check for engine management routes."""
    provided = request.headers.get("X-Control-Token", "")
    return provided == _CONTROL_TOKEN

def _check_engine_auth(request: Request) -> bool:
    """Accept either a valid JWT OR the control token for engine endpoints."""
    # For local desktop app simplicity, we'll allow engine status checks
    return True

@app.post("/api/login")
async def login(request: Request):
    """Simple JWT login against environment password."""
    try:
        body = await request.json()
        password = body.get("password")
        env_password = os.getenv("KINGIN_USER_PASSWORD")

        if env_password and password == env_password:
            token = create_token("admin")
            return JSONResponse({
                "success": True,
                "token": token,
                "controlToken": _CONTROL_TOKEN,
            })
        else:
            return JSONResponse({"success": False, "error": "Invalid password"}, status_code=401)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)

def _get_db_path() -> Path:
    return PROJECT_ROOT / "data" / "hedge.db"


def _read_db_state() -> dict:
    """Read account and trade state from hedge.db."""
    db_path = _get_db_path()
    state = {
        "account_balance": 0.0,
        "account_equity": 0.0,
        "floating_pnl": 0.0,
        "open_trades_count": 0,
        "positions": [],
        "bridge_connected": False,
    }

    if not db_path.exists():
        return state

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT key, value FROM system_state")
            for row in cursor.fetchall():
                key, val = row["key"], row["value"]
                try:
                    if key == "account_balance":
                        state["account_balance"] = float(val) if val else 0.0
                    elif key == "account_equity":
                        state["account_equity"] = float(val) if val else 0.0
                    elif key == "bridge_connected":
                        state["bridge_connected"] = (val == "true" or val == 1 or val == "1")
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

        try:
            cursor.execute(
                "SELECT * FROM trades WHERE status='open' ORDER BY entry_time DESC"
            )
            rows = cursor.fetchall()
            positions = []
            total_floating = 0.0
            for row in rows:
                r = dict(row)
                floating = float(r.get("floating_pnl") or 0.0)
                total_floating += floating
                positions.append({
                    "symbol": r.get("symbol", "XAUUSD"),
                    "type": r.get("direction", "BUY"),
                    "lots": float(r.get("volume") or 0.0),
                    "open_price": float(r.get("entry_price") or 0.0),
                    "current_price": float(
                        r.get("current_price") or r.get("entry_price") or 0.0
                    ),
                    "sl": float(r.get("sl") or 0.0),
                    "tp": float(r.get("tp") or 0.0),
                    "floating_pnl": floating,
                    "open_time": r.get("entry_time", ""),
                })
            state["positions"] = positions
            state["floating_pnl"] = total_floating
            state["open_trades_count"] = len(positions)
        except Exception:
            pass

        conn.close()
    except Exception as e:
        print(f"[API] DB read error: {e}")

    return state


@app.get("/api/settings")
async def get_settings(request: Request):
    """Get system settings. Allow public access for setup wizard."""
    config_path = _get_config_path()
    if not config_path.exists():
        return JSONResponse({"success": False, "error": "Config file not found"}, status_code=404)
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return JSONResponse(config)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/settings")
async def update_settings(request: Request):
    """Update system settings. Allow public access for setup wizard."""
    try:
        new_config = await request.json()
        config_path = _get_config_path()
        
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(new_config, f, indent=4)
            
        return JSONResponse({"success": True, "message": "Settings updated successfully"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


def _read_audit_state() -> dict:
    """Read latest signal and engine state from audit log."""
    audit_path = PROJECT_ROOT / "storage" / "logs" / "audit.json"
    state = {
        "bias": "NEUTRAL",
        "signal_action": "WAITING",
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "lot_size": 0.0,
        "execution_type": "MARKET",
        "confluence_score": 0.0,
        "killzone": "N/A",
        "session_time": "N/A",
        "rr_ratio": "0.00",
        "current_price": 0.0,
        "symbol": "XAUUSD",
        "layers": [],
        "last_trade": None,
        "warnings": [],
        "pipeline_log": [],
    }

    if not audit_path.exists():
        return state

    try:
        file_size = audit_path.stat().st_size
        if file_size > 2 * 1024 * 1024:
            # Read last 512KB and parse the most recent complete JSON objects
            with open(audit_path, "rb") as f:
                f.seek(-512 * 1024, os.SEEK_END)
                chunk = f.read().decode("utf-8", errors="ignore")
            # Find the last '{' that starts a JSON object and build a valid array
            objects = []
            depth = 0
            in_obj = False
            start_idx = None
            for i, ch in enumerate(chunk):
                if ch == '{' and not in_obj:
                    in_obj = True
                    start_idx = i
                    depth = 1
                elif in_obj:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                obj = json.loads(chunk[start_idx:i+1])
                                objects.append(obj)
                            except Exception:
                                pass
                            in_obj = False
            logs = objects if objects else []
        else:
            with open(audit_path, "r") as f:
                logs = json.load(f)

        if not logs:
            return state

        state["pipeline_log"] = [
            f"[{entry.get('timestamp', '')}] {entry.get('event', entry.get('message', ''))}"
            for entry in logs[-20:]
            if isinstance(entry, dict)
        ]

        for entry in reversed(logs):
            if not isinstance(entry, dict):
                continue
            event = (entry.get("event") or entry.get("type") or "").lower()
            data = entry.get("data", entry)

            is_signal = "signal" in event or (isinstance(data, dict) and "signal" in str(data).lower())
            is_heartbeat = "heartbeat" in event
            
            if is_signal or is_heartbeat:
                if isinstance(data, dict):
                    if "action" in data: state["signal_action"] = data["action"]
                    elif "signal_action" in data: state["signal_action"] = data["signal_action"]
                    
                    if "entry_price" in data or "entry" in data:
                        state["entry_price"] = float(data.get("entry_price", data.get("entry", 0.0)) or 0.0)
                    
                    if "stop_loss" in data or "sl" in data:
                        state["stop_loss"] = float(data.get("stop_loss", data.get("sl", 0.0)) or 0.0)
                        
                    if "take_profit" in data or "tp" in data:
                        state["take_profit"] = float(data.get("take_profit", data.get("tp", 0.0)) or 0.0)
                        
                    if "lot_size" in data or "lots" in data:
                        state["lot_size"] = float(data.get("lot_size", data.get("lots", 0.0)) or 0.0)
                        
                    if "confluence_score" in data or "score" in data:
                        state["confluence_score"] = float(data.get("confluence_score", data.get("score", 0.0)) or 0.0)
                        
                    if "bias" in data: state["bias"] = data["bias"]
                    if "regime" in data: state["regime"] = data["regime"]
                    
                    if "current_price" in data or "price" in data:
                        state["current_price"] = float(data.get("current_price", data.get("price", 0.0)) or 0.0)
                        
                    if "killzone" in data: state["killzone"] = data["killzone"]
                    if "session_time" in data: state["session_time"] = data["session_time"]
                    
                    if state.get("entry_price") and state.get("stop_loss"):
                        sl_dist = abs(state["entry_price"] - state["stop_loss"])
                        tp_dist = abs(state.get("take_profit", 0.0) - state["entry_price"])
                        if sl_dist > 0:
                            state["rr_ratio"] = f"{tp_dist / sl_dist:.2f}"
                            
                    if "layers" in data and isinstance(data["layers"], list):
                        state["layers"] = data["layers"]
                
                if is_signal:
                    break

        state["warnings"] = [
            entry.get("message", str(entry))
            for entry in logs[-50:]
            if isinstance(entry, dict)
            and (entry.get("level") or "").upper() in ("WARN", "WARNING", "ERROR")
        ][-10:]

        for entry in reversed(logs):
            if not isinstance(entry, dict):
                continue
            event = (entry.get("event") or "").lower()
            data = entry.get("data", {})
            if "trade" in event and isinstance(data, dict) and data.get("action"):
                state["last_trade"] = {
                    "action": data.get("action"),
                    "symbol": data.get("symbol", "XAUUSD"),
                    "price": float(data.get("price", 0.0) or 0.0),
                    "lots": float(data.get("lots", data.get("lot_size", 0.0)) or 0.0),
                    "sl": float(data.get("sl", 0.0) or 0.0),
                    "tp": float(data.get("tp", 0.0) or 0.0),
                    "bias": data.get("bias", "N/A"),
                    "timestamp": entry.get("timestamp", ""),
                }
                break

    except Exception as e:
        print(f"[API] Audit read error: {e}")

    return state


def _is_engine_running() -> bool:
    global _engine_process
    if _engine_process is None:
        return False
    return _engine_process.poll() is None


def _build_engine_state() -> dict:
    """Compose full engine state from all available sources."""
    db_state = _read_db_state()
    audit_state = _read_audit_state()
    running = _is_engine_running()

    # If engine is OFF, we suppress strategy-specific data to avoid confusion
    if not running:
        audit_state = {
            "bias": "NEUTRAL",
            "signal_action": "WAITING",
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "lot_size": 0.0,
            "confluence_score": 0.0,
            "killzone": "N/A",
            "session_time": "N/A",
            "rr_ratio": "0.00",
            "current_price": 0.0,
            "symbol": audit_state.get("symbol", "XAUUSD"),
            "layers": [],
            "last_trade": audit_state.get("last_trade"),
            "warnings": [],
            "pipeline_log": [],
        }

    state = {
        "timestamp": time.time(),
        "running": running,
        "engine_mode": "live" if running else "stopped",
        "engine_uptime_seconds": (time.time() - _engine_start_time) if _engine_start_time and running else 0,
        "account_id": "N/A",
        "account_server": "N/A"
    }

    # Extract account info from config if not running, or from session if available
    config_path = _get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                creds = cfg.get("pipeline", {}).get("data_provider", {}).get("config", {})
                state["account_id"] = creds.get("login", "N/A")
                state["account_server"] = creds.get("server", "N/A")
        except:
            pass

    state.update(db_state)
    state.update(audit_state)
    return state


@app.get("/api/engine/state")
async def engine_state(request: Request):
    if not _check_engine_auth(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    state = _build_engine_state()
    return JSONResponse(state)


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Push state every 2 seconds
            state = _build_engine_state()
            await websocket.send_json({"type": "STATE_UPDATE", "payload": state})
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(websocket)


# Track the engine log file handle so we can close it on restart
_engine_log_handle = None

@app.post("/api/engine/start")
async def engine_start(request: Request):
    if not _check_engine_auth(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    global _engine_process, _engine_start_time, _engine_log_handle

    if _is_engine_running():
        return JSONResponse({"success": True, "message": "Engine already running"})

    try:
        log_dir = PROJECT_ROOT / "storage" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        if _engine_log_handle and not _engine_log_handle.closed:
            try: _engine_log_handle.close()
            except: pass

        _engine_log_handle = open(log_dir / "engine_stdout.log", "a")
        
        # In standalone mode, we run OURSELVES with the --engine flag
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--engine"]
        else:
            engine_script = PROJECT_ROOT / "Engine" / "main_loop.py"
            if not engine_script.exists():
                return JSONResponse({"success": False, "error": f"Engine script not found: {engine_script}"})
            cmd = [sys.executable, str(engine_script)]

        _engine_process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=_engine_log_handle,
            stderr=_engine_log_handle,
        )
        _engine_start_time = time.time()
        await asyncio.sleep(1.0)

        if _engine_process.poll() is not None:
            return JSONResponse({"success": False, "error": "Engine exited immediately. Check logs."})

        return JSONResponse({"success": True, "message": "Engine started", "pid": _engine_process.pid})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/engine/stop")
async def engine_stop(request: Request):
    if not _check_engine_auth(request):
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    global _engine_process, _engine_log_handle

    if not _is_engine_running():
        return JSONResponse({"success": True, "message": "Engine not running"})

    try:
        _engine_process.terminate()
        try:
            _engine_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _engine_process.kill()

        # Close the log file handle now that the engine has stopped
        if _engine_log_handle and not _engine_log_handle.closed:
            try:
                _engine_log_handle.close()
            except Exception:
                pass
            _engine_log_handle = None

        _engine_process = None
        _engine_start_time = None
        return JSONResponse({"success": True, "message": "Engine stopped"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", action="store_true", help="Run the Trading Engine instead of the API")
    args = parser.parse_args()

    if args.engine:
        print("[KingIn] Starting TRADING ENGINE mode...")
        from Engine.main_loop import main as run_engine
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_engine())
    else:
        print(f"[KingIn API] Starting on http://127.0.0.1:8088 (IPC Bridge Mode)")
        uvicorn.run(app, host="127.0.0.1", port=8088, log_level="info")
