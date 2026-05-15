"""Data Poller."""
import asyncio
from datetime import datetime

async def start_data_poller():
    while True:
        try:
            from data.buffers import add_candle, add_tick
            price = 2680.0 + (datetime.now().timestamp() % 100) * 0.01
            add_tick({"time": datetime.now().isoformat(), "bid": price, "ask": price + 0.5, "symbol": "XAUUSD"})
            add_candle("M5", {"time": datetime.now().isoformat(), "open": price, "high": price + 2, "low": price - 2, "close": price + 1, "volume": 100})
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[POLLER] Error: {e}")
            await asyncio.sleep(5)