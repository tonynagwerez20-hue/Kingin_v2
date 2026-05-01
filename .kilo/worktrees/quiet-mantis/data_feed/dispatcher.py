import asyncio
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional

import websockets

# ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Initialize independent buffers
ohlc_buffers: Dict[str, deque] = {
    "M5": deque(maxlen=500),
    "M15": deque(maxlen=500),
    "H1": deque(maxlen=500)
}

from support.env_loader import get_env

# Try to import DB
try:
    from storage.hedge_db import HedgeDB
except (ImportError, ModuleNotFoundError):
    HedgeDB = None

# Try to import configurations
try:
    from support.configurations import configurations as cfg
    SYSTEM_CONFIG = getattr(cfg, "SYSTEM_CONFIG", {})
except (ImportError, ModuleNotFoundError):
    SYSTEM_CONFIG = {}


# Local Delta Buffers (Shared via import)
# v4.0: Store dicts with {"delta": x, "max": y, "min": z}
delta_buffers: Dict[str, deque] = {
    "M1": deque(maxlen=500),
    "M5": deque(maxlen=500),
    "M15": deque(maxlen=500),
    "H1": deque(maxlen=500),
}

# Global Latest Tick Data (for real-time dashboard)
latest_tick: Dict[str, Any] = {
    "price": 0.0,
    "bid": 0.0,
    "ask": 0.0,
    "volume": 0.0,
    "timestamp": 0.0,
    "symbol": "XAUUSD"
}

def dispatch_batch(source_data: List[Dict[str, Any]], target_buffer: deque):
    """
    Clears the target buffer and loads a new batch of data.
    Ensures a fresh, clean window of time.
    """
    if not isinstance(source_data, list):
        return
        
    target_buffer.clear()
    target_buffer.extend(source_data)

class DataDispatcher:
    def __init__(self, ws_url: str = None, broadcast_func: Optional[Callable[[Dict], Any]] = None):
        self.ws_url = ws_url or get_env("SIERRA_WS_URL", "ws://localhost:9000")
        self.broadcast_func = broadcast_func

    async def run(self):
        """Main loop: Connects to Sierra and distributes data."""
        while True:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    print(f"[Dispatcher] Connected to Sierra WS at {self.ws_url}")
                    async for msg in ws:
                        try:
                            payload = json.loads(msg)
                        except Exception:
                            continue
                        
                        await self._process_message(payload)
                        
            except Exception as e:
                print(f"[Dispatcher] Connection error: {e}; reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _process_message(self, payload: Dict[str, Any]):
        msg_type = payload.get("type")
        tf = payload.get("tf")

        if msg_type == "ohlc" and tf:
            self._handle_ohlc(tf, payload)
        elif msg_type == "delta" and tf:
            self._handle_delta(tf, payload)
        
        # Broadcast to API listeners
        if self.broadcast_func:
            await self.broadcast_func(payload)

    def _handle_ohlc(self, tf: str, payload: Dict[str, Any]):
        candle = {
            "open": payload.get("open"),
            "high": payload.get("high"),
            "low": payload.get("low"),
            "close": payload.get("close"),
            "time": payload.get("time"),
        }

        # Update Latest Tick (use M5 as primary source)
        if tf == "M5" and candle.get("close"):
            latest_tick["price"] = candle["close"]
            latest_tick["timestamp"] = candle.get("time", 0)
            latest_tick["volume"] = payload.get("volume", 0)
            # Estimate bid/ask from spread (default 1.5 pips)
            spread_half = 0.75
            latest_tick["bid"] = candle["close"] - spread_half
            latest_tick["ask"] = candle["close"] + spread_half

        # Update Local Buffers Directly
        if tf in ohlc_buffers:
            ohlc_buffers[tf].append(candle)
        
        # Persist to DB
        if HedgeDB:
            try:
                db = HedgeDB()
                db.insert_candle(
                    payload.get("symbol", "XAUUSD"), 
                    tf, 
                    candle["open"], 
                    candle["high"], 
                    candle["low"], 
                    candle["close"], 
                    int(payload.get("time", 0) or 0)
                )
                db.close()
            except Exception as db_err:
                print(f"[Dispatcher] DB Error: {db_err}")

    def _handle_delta(self, tf: str, payload: Dict[str, Any]):
        # v4.0 support for multi-column delta
        val = float(payload.get("value", 0.0))
        mx = float(payload.get("max", val))
        mn = float(payload.get("min", val))
        
        delta_struct = {"delta": val, "max": mx, "min": mn}
        
        # Update Delta Buffers
        if tf in delta_buffers:
            delta_buffers[tf].append(delta_struct)
            
        # Update OHLC Buffer (Merge Delta)
        if tf in ohlc_buffers:
            buf = ohlc_buffers[tf]
            if buf:
                last_candle = buf[-1]
                last_candle["delta"] = val
                last_candle["max_delta"] = mx
                last_candle["min_delta"] = mn
