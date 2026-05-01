"""WebSocket-based datafeed connector and subscription server.

Background behavior:
- Starts a background dispatcher (`dispatcher.py`) which connects to Sierra Charts.
- Serves data from buffers populated by the dispatcher.

API:
- GET /ohlc?tf=M5&limit=50 (HTTP) — returns last N candles
- GET /delta?tf=M5&limit=4 (HTTP) — returns delta struct for logic
- WS  /ws — subscribe to live updates (server pushes JSON messages received from Sierra)
"""
import asyncio
import json
import sys
import threading
import time
import sqlite3
from pathlib import Path
from typing import Any, Dict, List
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import JSONResponse
import uvicorn

from fastapi.middleware.cors import CORSMiddleware

# ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from data_feed.dispatcher import DataDispatcher, delta_buffers, ohlc_buffers, latest_tick
except ImportError:
    # Check if we need to look in data_feed directly
    feed_path = project_root / "data feed"
    sys.path.append(str(feed_path))
    from dispatcher import DataDispatcher, delta_buffers, ohlc_buffers, latest_tick

try:
    from support.env_loader import get_env
    from data.csv_processor import CSVBatchProcessor
except ImportError:
    get_env = lambda k, d: d
    CSVBatchProcessor = None
 
# Shared DTC client reference for status checks
dtc_client_instance = None

# Track server start time for uptime calculation
server_start_time = time.time()

# Latency tracking for MT5
mt5_latency_history = deque(maxlen=10)
last_mt5_ping_time = 0


# --- LOGGING SETUP ---
class LoggerWriter:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        # self.log.flush() # Flush is handled by flush() or explicitly if needed, but safe to let OS handle slightly buffering for perf, or force strict persistence.
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def isatty(self):
        return True  # Cheat to satisfy libraries checking for TTY

    def fileno(self):
        return self.terminal.fileno()

# Redirect stdout/stderr to file + console
log_dir = project_root / "storage" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
sys.stdout = LoggerWriter(log_dir / "server_live.log")
sys.stderr = sys.stdout

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


# Forward declaration of lifespan for FastAPI
async def lifespan(app: FastAPI):
    # Determine Mode from Modular Config or ENV
    config_path = project_root / "config" / "trading_params_lite.json"
    default_mode = "CSV"
    symbol = "XAUUSD"
    
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                active_source = cfg.get("pipeline", {}).get("active_data_source", "MT5_PROVIDER")
                symbol = cfg.get("trading", {}).get("symbol", "XAUUSD")
                if active_source == "MT5_PROVIDER":
                    default_mode = "MT5"
                elif active_source == "SIERRA_PROVIDER":
                    default_mode = "DTC"
        except Exception as e:
            print(f"[Server] Failed to parse modular config, falling back to ENV/Legacy: {e}")

    mode = get_env("DATA_SOURCE_TYPE", default_mode)
    
    if mode == "MT5":
        print(f"[Server] Starting in MT5 Polling Mode (Symbol: {symbol})")
        from data_feed.mt5_provider import MT5DataProvider
        
        # Load MT5 specific config
        mt5_cfg = {}
        if config_path.exists():
             with open(config_path, "r") as f:
                  full_cfg = json.load(f)
                  mt5_cfg = full_cfg.get("pipeline", {}).get("data_provider", {}).get("config", {})
        
        provider = MT5DataProvider(mt5_cfg)
        if provider.connect():
            async def mt5_poller():
                print("[Server] MT5 Poller Started")
                while True:
                    try:
                        # Poll M5, M15, H1
                        for tf in ["M5", "M15", "H1"]:
                            candles = provider.get_latest_candles(symbol, tf, 20)
                            if candles:
                                if tf in ohlc_buffers:
                                    # Atomic replace for smooth API results
                                    for c in candles:
                                        # Simple deduplication based on time
                                        existing_times = [x.get("time") for x in ohlc_buffers[tf]]
                                        if c["time"] not in existing_times:
                                             ohlc_buffers[tf].append(c)
                                             
                                # Update latest tick if M5
                                if tf == "M5" and candles:
                                    last = candles[-1]
                                    latest_tick["price"] = last["close"]
                                    latest_tick["bid"] = last["close"] - 0.05 # Mocked spread if not avail
                                    latest_tick["ask"] = last["close"] + 0.05
                                    latest_tick["timestamp"] = time.time()
                            else:
                                if not provider.is_connected():
                                    print("[Server] MT5 Disconnected during polling, attempting reconnect...")
                                    provider.connect()
                                    
                        await asyncio.sleep(5) # Poll every 5s
                    except Exception as e:
                        import traceback
                        print(f"[Server] MT5 Polling Exception: {e}")
                        traceback.print_exc()
                        await asyncio.sleep(10)

            poller_task = asyncio.create_task(mt5_poller())
            yield
            poller_task.cancel()
            provider.shutdown()
        else:
            print("[Server] ERROR: Failed to connect to MT5. Check credentials and ensure MT5 is running.")
            yield

    elif mode == "CSV" and CSVBatchProcessor:
        print("[Server] Starting in CSV Mode (Multi-File)")
        
        # Define files to watch (Hardcoded default or ENV)
        files_config = [
            ("H1", get_env("SIERRA_H1_PATH", "data_feed/sierra_H1.txt")),
            ("M15", get_env("SIERRA_M15_PATH", "data_feed/sierra_M15.txt")),
            ("M5", get_env("SIERRA_M5_PATH", "data_feed/sierra_M5.txt"))
        ]
        
        processors = []
        loop = asyncio.get_running_loop()
        
        for tf, path_str in files_config:
            file_path = project_root / path_str
            # Ensure path exists or use absolute if provided
            if not file_path.exists() and Path(path_str).exists():
                 file_path = Path(path_str)
            
            if not file_path.exists():
                print(f"[Server] WARNING: {tf} File {file_path} not found. Creating empty...")
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.touch()

            print(f"[Server] Watching {tf} -> {file_path}")

            # Callback factory to capture TF
            def make_callback(timeframe):
                def cb(candle):
                    if SUBSCRIBERS:
                        asyncio.run_coroutine_threadsafe(
                             _broadcast({"type": "ohlc", "tf": timeframe, **candle}),
                             loop
                        )
                    
                    if timeframe in ohlc_buffers:
                         ohlc_buffers[timeframe].append(candle)
                    
                    if timeframe in delta_buffers:
                        # v4.0: Store full struct
                        delta_buffers[timeframe].append({
                            "delta": candle.get("delta", 0.0),
                            "max": candle.get("max_delta", candle.get("delta", 0.0)),
                            "min": candle.get("min_delta", candle.get("delta", 0.0))
                        })

                return cb

            proc = CSVBatchProcessor(str(file_path), make_callback(tf), batch_delay=1.0)
            processors.append(proc)
            loop.run_in_executor(None, proc.start)
            
        yield
        for p in processors: p.stop()
        
    elif mode == "DTC":
        print("[Server] Starting in DTC Protocol Mode")
        import data_feed.dtc_client as dtc_client
        
        host = get_env("SIERRA_DTC_HOST", "127.0.0.1")
        port_live = int(get_env("SIERRA_DTC_PORT", 11099))
        symbol = get_env("SIERRA_SYMBOL", "XAUUSD")
        
        # v4.0 HYBRID MODE: Always attempt to load history from CSV first
        print("[Server] [HYBRID] Pre-loading History from CSV files...")
        
        files_config = [
            ("H1", get_env("SIERRA_H1_PATH", "data_feed/sierra_H1.txt")),
            ("M15", get_env("SIERRA_M15_PATH", "data_feed/sierra_M15.txt")),
            ("M5", get_env("SIERRA_M5_PATH", "data_feed/sierra_M5.txt"))
        ]
        
        loop = asyncio.get_running_loop()
        
        for tf, path_str in files_config:
            file_path = project_root / path_str
            # Try absolute if relative fails
            if not file_path.exists() and Path(path_str).exists():
                 file_path = Path(path_str)

            if file_path.exists():
                print(f"[Server] Loading {tf} from {file_path}...")
                try:
                    # Define robust callback matching CSV mode
                    def hybrid_cb(candle):
                        # 1. Update OHLC
                        if tf in ohlc_buffers:
                             ohlc_buffers[tf].append(candle)
                        
                        # 2. Update Delta (Critical for Logic)
                        if tf in delta_buffers:
                             delta_buffers[tf].append({
                                 "delta": candle.get("delta", 0.0),
                                 "max": candle.get("max_delta", candle.get("delta", 0.0)),
                                 "min": candle.get("min_delta", candle.get("delta", 0.0))
                             })
                        
                        # 3. Update Latest Tick (if M5)
                        if tf == "M5":
                            # A bit hacky, but ensures dashboard isn't empty
                            pass

                    # Run Processor Once
                    proc = CSVBatchProcessor(str(file_path), hybrid_cb)
                    await loop.run_in_executor(None, proc.process_file_once)
                    
                    count = len(ohlc_buffers.get(tf, []))
                    print(f"[Server]  -> Loaded {count} bars for {tf}")
                    
                except Exception as e:
                    print(f"[Server]  -> Failed to load {tf}: {e}")
            else:
                print(f"[Server]  -> File not found: {file_path}")
        
        # v3.9 Multi-Symbol Support
        # Note: IGOF uses GC, ZN, 6E, ES. We should pass all if needed, or just the main symbol if disabled.
        # Ideally, we pass ALL required symbols so the client is ready even if IGOF is disabled in main_loop.
        # But to be safe and simple, let's just pass the main symbol as a list for now, 
        # OR better: pass the IGOF set if mode=DTC? 
        # User wants "dormant", so let's just pass the single symbol to keep it lightweight?
        # No, "dormant" means code is there but not used. The client SHOULD have the capability.
        # Let's pass [symbol] to fix the error.
        client = dtc_client.DTCClient(host=host, port_live=port_live, symbols=[symbol])
        global dtc_client_instance
        dtc_client_instance = client
        client.start()
        
        yield
        
        client.running = False
        client._disconnect_all()
        dtc_client_instance = None

    else:
        print("[Server] Starting in WebSocket Mode")
        dispatcher = DataDispatcher(broadcast_func=_broadcast)
        task = asyncio.create_task(dispatcher.run())
        yield
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

app = FastAPI(lifespan=lifespan)

# Add CORS middleware to allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket subscribers set
SUBSCRIBERS: List[WebSocket] = []


async def _broadcast(message: Dict[str, Any]) -> None:
    data = json.dumps(message)
    to_remove = []
    for ws in list(SUBSCRIBERS):
        try:
            await ws.send_text(data)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        try:
            SUBSCRIBERS.remove(ws)
        except ValueError:
            pass

async def broadcast_audit(entry: Dict[str, Any]):
    """Broadcasts an audit log entry to all connected WebSockets."""
    await _broadcast({
        "type": "audit",
        "data": entry
    })



def _standardize_tf(tf: str) -> str:
    """Normalize timeframe string for consistent buffer lookups."""
    if not tf: return "M5"
    res = tf.strip().upper()
    # Handle common aliases if any (e.g. '1H' -> 'H1')
    if res == "1H": return "H1"
    if res == "15M": return "M15"
    if res == "5M": return "M5"
    return res

def _candles_from_memory(timeframe: str, limit: int, symbol: str = "XAUUSD") -> List[Dict[str, Any]]:
    """Retrieve candles from shared Aggregator buffers."""
    tf_key = _standardize_tf(timeframe)
    # Try specific key first
    key = f"{symbol}_{tf_key}"
    if symbol == "XAUUSD" and key not in ohlc_buffers:
        key = tf_key # Fallback to legacy keys
        
    dq = ohlc_buffers.get(key)
    if dq is None:
        # Fallback check if buffers are keys differently
        return []
    # Convert deque to list
    data = list(dq)
    return data[-limit:]


def build_delta_struct(timeframe: str, limit: int = 4) -> Dict[str, List[float]]:
    """Build the delta structure required by delta_logic.py."""
    tf_key = _standardize_tf(timeframe)
    dq = delta_buffers.get(tf_key)
    if dq is None or len(dq) == 0:
        return {"delta": [], "max": [], "min": [], "cumulative": []}
    
    # Get last N elements
    arr = list(dq)
    raw = arr[-limit:]
    
    # delta_logic expects 'd' to be reversed (d0 is index 0 = most recent)
    rev_raw = list(reversed(raw))
    
    # v4.0: Extract from struct if possible, else fallback to scalar calc
    delta_list = []
    max_list = []
    min_list = []
    
    # Handle both new struct format and old scalar format gracefully
    for item in rev_raw:
        if isinstance(item, dict):
            delta_list.append(item.get("delta", 0.0))
            max_list.append(item.get("max", item.get("delta", 0.0)))
            min_list.append(item.get("min", item.get("delta", 0.0)))
        else:
            delta_list.append(float(item))
            # If scalar, Max/Min defaults to value for single bar
            max_list.append(float(item))
            min_list.append(float(item))

    # delta_logic expects dmax/dmin to be cumulative for reversal detection?
    # NO: evaluate_delta uses dmax[0] meaning peak within that bar.
    # So we should return the raw per-bar peaks.

    # Cumulative sum
    cumulative = []
    s = 0.0
    for val in delta_list:
        s += val
        cumulative.append(s)
        
    return {"delta": delta_list, "max": max_list, "min": min_list, "cumulative": cumulative}


@app.get("/ohlc")
async def http_ohlc(request: Request):
    tf = request.query_params.get("tf", "M5")
    limit = int(request.query_params.get("limit", 500))
    symbol = request.query_params.get("symbol", "XAUUSD")
    # print(f"[API] GET /ohlc?tf={tf}&limit={limit}&symbol={symbol}")
    data = _candles_from_memory(tf, limit, symbol)
    return JSONResponse({"timeframe": tf, "symbol": symbol, "candles": data})


@app.get("/delta")
async def http_delta(request: Request):
    tf = request.query_params.get("tf", "M5")
    limit = int(request.query_params.get("limit", 500))
    data = build_delta_struct(tf, limit)
    return JSONResponse(data)

@app.get("/depth")
async def http_depth(request: Request):
    """Returns DOM snapshot for a symbol"""
    symbol = request.query_params.get("symbol", "XAUUSD")
    # Need access to DTC client
    if dtc_client_instance and dtc_client_instance.running:
        # Map symbol to internal ID or use directly if depth_engines is keyed by symbol
        if symbol in dtc_client_instance.depth_engines:
            snapshot = dtc_client_instance.depth_engines[symbol].get_snapshot()
            return JSONResponse({"symbol": symbol, "bids": snapshot["bids"], "asks": snapshot["asks"]})
    
    return JSONResponse({"symbol": symbol, "bids": {}, "asks": {}})


@app.get("/spread")
async def get_spread():
    """Returns the current market spread. Derived from latest M5 candle data if available."""
    # In a real environment, this would come from a live ticker feed.
    # For this implementation, we check the latest M5 candle's metadata or use a default.
    dq = ohlc_buffers.get("M5")
    spread = 1.5 # Default fallback
    if dq and len(dq) > 0:
        last_candle = dq[-1]
        # In Sierra exports, spread is often a custom column. 
        # We'll check if it exists, otherwise use a realistic random-ish default or fixed value.
        spread = last_candle.get("spread", 1.5)
    
    return JSONResponse({"spread": spread, "symbol": "XAUUSD"})

@app.get("/latest-price")
async def get_latest_price():
    """Ultra-lightweight endpoint: Returns ONLY the current price.
    Perfect for real-time tickers without the overhead of fetching 500 bars.
    """
    # Try to get from latest_tick first (DTC live updates)
    if latest_tick.get("price", 0) > 0:
        return JSONResponse({
            "price": latest_tick["price"],
            "bid": latest_tick.get("bid", latest_tick["price"] - 0.75),
            "ask": latest_tick.get("ask", latest_tick["price"] + 0.75),
            "timestamp": latest_tick.get("timestamp", time.time())
        })
    
    # Fallback to M5 buffer
    dq = ohlc_buffers.get("M5")
    if dq and len(dq) > 0:
        last = dq[-1]
        price = last.get("close", 0)
        return JSONResponse({
            "price": price,
            "bid": price - 0.75,
            "ask": price + 0.75,
            "timestamp": last.get("time", time.time())
        })
    
    # No data available
    return JSONResponse({"price": 0, "bid": 0, "ask": 0, "timestamp": 0})

@app.get("/latest-tick")
async def get_latest_tick():
    """Lightweight endpoint: Returns current price + volume + delta.
    Use this for live monitoring without fetching full candle history.
    """
    dq = ohlc_buffers.get("M5")
    if dq and len(dq) > 0:
        last = dq[-1]
        raw_ts = last.get("time", time.time())
        # pandas Timestamp (and similar) are not JSON-serializable – convert to float epoch
        if hasattr(raw_ts, "timestamp"):
            raw_ts = raw_ts.timestamp()
        else:
            try:
                raw_ts = float(raw_ts)
            except (TypeError, ValueError):
                raw_ts = time.time()
        return JSONResponse({
            "price": last.get("close", 0),
            "bid": latest_tick.get("bid", last.get("close", 0) - 0.75),
            "ask": latest_tick.get("ask", last.get("close", 0) + 0.75),
            "volume": last.get("volume", 0),
            "delta": last.get("delta", 0),
            "timestamp": raw_ts,
            "symbol": "XAUUSD"
        })
    
    return JSONResponse(latest_tick)

@app.get("/debug/buffers")
async def debug_buffers():
    """Diagnostic endpoint to inspect buffer counts."""
    return JSONResponse({
        "ohlc_keys": list(ohlc_buffers.keys()),
        "ohlc_counts": {k: len(v) for k,v in ohlc_buffers.items()},
        "delta_keys": list(delta_buffers.keys()),
        "delta_counts": {k: len(v) for k,v in delta_buffers.items()},
        "latest_tick": latest_tick
    })

@app.get("/status/detailed")
async def get_detailed_status():
    """Returns comprehensive system status with connection details and uptime."""
    mode = _get_current_mode()
    current_time = time.time()
    
    # 1. Feed Connection Details
    feed_status = {
        "connected": False,
        "synced": False,
        "uptime": 0,
        "last_heartbeat": 0,
        "mode": mode
    }
    
    if mode == "DTC" and dtc_client_instance:
        feed_status["connected"] = dtc_client_instance.running
        feed_status["synced"] = dtc_client_instance.is_synced
        feed_status["last_heartbeat"] = dtc_client_instance.last_live_hb
        if hasattr(dtc_client_instance, '_start_time'):
            feed_status["uptime"] = current_time - dtc_client_instance._start_time
    elif mode in ["CSV", "MT5"]:
        dq = ohlc_buffers.get("M5")
        if dq and len(dq) > 0:
            last_time = dq[-1].get("time", 0)
            if hasattr(last_time, "timestamp"):
                last_time = last_time.timestamp()
            else:
                try: last_time = float(last_time)
                except (TypeError, ValueError): last_time = 0

            if current_time - last_time < 300:
                feed_status["connected"] = True
                feed_status["synced"] = True
                feed_status["last_heartbeat"] = last_time
    
    # 2. Broker Sync Details
    broker_status = {
        "connected": False,
        "last_sync": 0,
        "socket_status": "UNKNOWN"
    }
    
    db_path = project_root / "data" / "hedge.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key='balance_last_sync'")
            sync_row = cursor.fetchone()
            if sync_row:
                last_sync = float(sync_row[0])
                broker_status["last_sync"] = last_sync
                if current_time - last_sync < 120:
                    broker_status["connected"] = True
                    broker_status["socket_status"] = "ACTIVE"
            conn.close()
        except Exception as e:
            print(f"[Server] Detailed status DB error: {e}")
            
    return JSONResponse({
        "feed": feed_status,
        "broker": broker_status,
        "engine": {
            "status": "OK",
            "uptime": current_time - server_start_time
        },
        "server_uptime": current_time - server_start_time
    })

@app.get("/mt5/latency")
async def get_mt5_latency():
    """Measures and returns MT5 EA connection latency."""
    global last_mt5_ping_time, mt5_latency_history
    
    # Import bridge dynamically
    try:
        from execution.bridge import Bridge
        bridge = Bridge()
        
        # Measure latency
        start = time.time()
        latency_ms = bridge.ping_latency()
        
        if latency_ms is not None:
            mt5_latency_history.append(latency_ms)
            last_mt5_ping_time = time.time()
            
            avg_latency = sum(mt5_latency_history) / len(mt5_latency_history) if mt5_latency_history else 0
            
            return JSONResponse({
                "current_latency_ms": latency_ms,
                "average_latency_ms": avg_latency,
                "history": list(mt5_latency_history),
                "last_ping": last_mt5_ping_time,
                "status": "GOOD" if latency_ms < 50 else "WARNING" if latency_ms < 100 else "CRITICAL"
            })
        else:
            return JSONResponse({
                "error": "MT5 EA not responding",
                "current_latency_ms": 0,
                "average_latency_ms": 0,
                "status": "DISCONNECTED"
            })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "current_latency_ms": 0,
            "average_latency_ms": 0,
            "status": "ERROR"
        })

@app.get("/trades/realtime")
async def get_realtime_trades():
    """Returns real-time trade updates optimized for frequent polling."""
    db_path = project_root / "data" / "hedge.db"
    if not db_path.exists():
        return JSONResponse({"open": [], "closed": []})
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get open trades
        cursor.execute("SELECT * FROM trades WHERE status='open' ORDER BY entry_time DESC")
        open_rows = cursor.fetchall()
        open_trades = [dict(row) for row in open_rows]
        
        # Get recent closed trades (last 20)
        cursor.execute("SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT 20")
        closed_rows = cursor.fetchall()
        closed_trades = [dict(row) for row in closed_rows]
        
        conn.close()
        
        return JSONResponse({
            "open": open_trades,
            "closed": closed_trades,
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "open": [], "closed": []}, status_code=500)

@app.get("/market/realtime")
async def get_realtime_market():
    """Returns consolidated real-time market data in a single endpoint."""
    # Get latest price from tick buffer
    price_data = {
        "price": 0,
        "bid": 0,
        "ask": 0,
        "volume": 0,
        "timestamp": 0
    }
    
    if latest_tick.get("price", 0) > 0:
        price_data = {
            "price": latest_tick["price"],
            "bid": latest_tick.get("bid", latest_tick["price"] - 0.75),
            "ask": latest_tick.get("ask", latest_tick["price"] + 0.75),
            "volume": latest_tick.get("volume", 0),
            "timestamp": latest_tick.get("timestamp", time.time())
        }
    else:
        # Fallback to M5 buffer
        dq = ohlc_buffers.get("M5")
        if dq and len(dq) > 0:
            last = dq[-1]
            price = last.get("close", 0)
            price_data = {
                "price": price,
                "bid": price - 0.75,
                "ask": price + 0.75,
                "volume": last.get("volume", 0),
                "timestamp": last.get("time", time.time())
            }
    
    # Get broker spread from MT5
    spread = 1.5  # Default
    try:
        from execution.bridge import Bridge
        bridge = Bridge()
        mt5_spread = bridge.get_market_spread()
        if mt5_spread is not None:
            spread = mt5_spread
    except:
        pass
    
    return JSONResponse({
        **price_data,
        "spread": spread,
        "symbol": "XAUUSD"
    })
 
def _get_current_mode() -> str:
    """Helper to detect mode from config or env."""
    config_path = project_root / "config" / "trading_params_lite.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                active_source = cfg.get("pipeline", {}).get("active_data_source", "")
                if active_source == "MT5_PROVIDER": return "MT5"
                if active_source == "SIERRA_PROVIDER": return "DTC"
        except: pass
    return get_env("DATA_SOURCE_TYPE", "CSV")

@app.get("/status")
async def get_status():
    """Returns the current system status, including mode, sync state, balance, and component health."""
    mode = _get_current_mode()
    
    # 1. Data Feed Health
    feed_health = "DISCONNECTED"
    is_synced = False
    if mode == "DTC" and dtc_client_instance:
        feed_health = "OK" if dtc_client_instance.running else "DISCONNECTED"
        is_synced = dtc_client_instance.is_synced
    elif mode in ["CSV", "MT5"] or mode != "DTC":
         # Check if we have recent data in buffers
         dq = ohlc_buffers.get("M5")
         if dq and len(dq) > 0:
             last_time = dq[-1].get("time", 0)
             if hasattr(last_time, "timestamp"):
                 last_time = last_time.timestamp()
             else:
                 try: last_time = float(last_time)
                 except (TypeError, ValueError): last_time = 0
                 
             if time.time() - last_time < 300: # Within 5 mins
                 feed_health = "OK"
                 is_synced = True

    # 2. MT5 / Bridge Health & Balance
    balance = 0.0
    mt5_health = "DISCONNECTED"
    
    db_path = project_root / "data" / "hedge.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key='account_balance'")
            row = cursor.fetchone()
            if row:
                balance = float(json.loads(row[0])) if not isinstance(row[0], (int, float)) else float(row[0])
            
            cursor.execute("SELECT value FROM system_state WHERE key='balance_last_sync'")
            sync_row = cursor.fetchone()
            if sync_row:
                last_sync = float(sync_row[0])
                if time.time() - last_sync < 120: # Updated within 2 mins
                    mt5_health = "OK"
            conn.close()
        except Exception as e:
            print(f"[Server] Status DB error: {e}")

    # 3. Engine Health
    engine_health = "OK"
    
    return JSONResponse({
        "mode": mode,
        "is_synced": is_synced,
        "state": "ACTIVE" if feed_health == "OK" else "INITIALIZING",
        "balance": balance,
        "health": {
            "feed": feed_health,
            "engine": engine_health,
            "broker_sync": mt5_health
        }
    })

@app.get("/audit")
async def get_audit_logs(limit: int = 50):
    """Returns the latest signal and execution audit logs."""
    audit_path = project_root / "storage" / "logs" / "audit.json"
    if not audit_path.exists():
        return JSONResponse([])
    try:
        with open(audit_path, "r") as f:
            data = json.load(f)
            # Filter for strategy and execution events
            relevant = [
                entry for entry in reversed(data)
                if entry.get("module") in ["STRATEGY", "CRO", "EXECUTION"]
            ]
            return JSONResponse(relevant[:limit])
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/audit/broadcast")
async def post_audit_broadcast(request: Request):
    """Allows external components to broadcast audit events via WebSocket."""
    try:
        entry = await request.json()
        await broadcast_audit(entry)
        return JSONResponse({"status": "SUCCESS"})
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

@app.get("/trades")
async def get_trades(status: str = "all", limit: int = 50):
    """Returns trade history from the SQLite database."""
    db_path = project_root / "data" / "hedge.db"
    if not db_path.exists():
        return JSONResponse([])
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status == "open":
            cursor.execute("SELECT * FROM trades WHERE status='open' ORDER BY entry_time DESC LIMIT ?", (limit,))
        elif status == "closed":
            cursor.execute("SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,))
            
        rows = cursor.fetchall()
        trades = [dict(row) for row in rows]
        conn.close()
        return JSONResponse(trades)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/settings")
async def get_settings():
    """Returns the current system settings from the database."""
    db_path = project_root / "data" / "hedge.db"
    default_settings = {
        "trading": {
            "symbol": "XAUUSD",
            "default_lot_size": 0.01,
            "default_sl_pips": 20
        },
        "risk": {
            "max_risk_per_trade_pct": 1.0,
            "max_daily_loss_pct": 5.0,
            "max_concurrent_trades": 3
        },
        "data_feed": {
            "mode": get_env("DATA_SOURCE_TYPE", "DTC"),
            "host": get_env("SIERRA_DTC_HOST", "127.0.0.1"),
            "port": int(get_env("SIERRA_DTC_PORT", 11099))
        },
        "advanced": {
            "trailing_stop_pips": 10,
            "breakeven_pips": 5,
            "max_spread_allowed": 2.5,
            "trading_session_start": "08:00",
            "trading_session_end": "20:00"
        }
    }
    
    if not db_path.exists():
        return JSONResponse(default_settings)
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key='app_settings'")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            stored_settings = json.loads(row[0])
            # Merge defaults for any missing keys
            for category, values in default_settings.items():
                if category not in stored_settings:
                    stored_settings[category] = values
                else:
                    for k, v in values.items():
                        if k not in stored_settings[category]:
                            stored_settings[category][k] = v
            return JSONResponse(stored_settings)
            
        return JSONResponse(default_settings)
    except Exception as e:
        print(f"[Server] Error fetching settings: {e}")
        return JSONResponse(default_settings)

@app.post("/settings")
async def save_settings(request: Request):
    """Saves system settings to the database."""
    try:
        settings_data = await request.json()
        db_path = project_root / "data" / "hedge.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)", 
                       ("app_settings", json.dumps(settings_data)))
        conn.commit()
        conn.close()
        
        return JSONResponse({"status": "SUCCESS", "message": "Settings saved successfully"})
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)


@app.get("/backtest/signals")
async def get_backtest_signals():
    """Returns the list of recorded signals from the backtest CSV file."""
    signals_path = project_root / "data" / "backtest_signals.csv"
    if not signals_path.exists():
        return JSONResponse({"status": "WARNING", "message": "No backtest signals found."})
    
    import pandas as pd
    try:
        df = pd.read_csv(signals_path)
        return JSONResponse(df.to_dict(orient="records"))
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

@app.post("/backtest/simulate")
async def run_simulation(request: Request):
    """Triggers a Monte Carlo simulation on the recorded backtest signals."""
    try:
        from support.statistical.monte_carlo_engine import MonteCarloEngine
        params = await request.json()
        
        engine = MonteCarloEngine()
        results = engine.run_simulation(
            iterations=params.get("iterations", 1000),
            slippage_pips=params.get("slippage", 1.5),
            initial_balance=params.get("initial_balance", 10000.0)
        )
        
        return JSONResponse(results)
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)

# Track active backtest process
backtest_process = None

@app.post("/backtest/run")
async def run_backtest_endpoint(request: Request):
    """Launches the backtest orchestrator in a sub-process."""
    global backtest_process
    
    try:
        # 1. Kill existing if running
        if backtest_process and backtest_process.poll() is None:
            print("[Server] Terminating existing backtest process...")
            backtest_process.terminate()
            try:
                backtest_process.wait(timeout=3)
            except:
                backtest_process.kill()
        
        # 2. Launch run_backtest.py
        # Use venv python if possible
        python_cmd = sys.executable
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            python_cmd = str(venv_python)
            
        print(f"[Server] Launching backtest: {python_cmd} run_backtest.py --mode=DTC")
        
        # CREATE_NEW_PROCESS_GROUP or similar to avoid signal propagation if needed, 
        # but for simple trigger, Popen is fine.
        backtest_process = subprocess.Popen(
            [python_cmd, "run_backtest.py", "--mode=DTC"],
            cwd=project_root,
            # Don't capture stdout to avoid pipe filling up and blocking, 
            # or redirect to a log file.
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        return JSONResponse({"status": "SUCCESS", "message": "Backtest initiated in background."})
    except Exception as e:
        return JSONResponse({"status": "ERROR", "message": str(e)}, status_code=500)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    SUBSCRIBERS.append(ws)
    try:
        while True:
            # Client just listens.
            await ws.receive_text()
    except WebSocketDisconnect:
        try:
            SUBSCRIBERS.remove(ws)
        except ValueError:
            pass


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
