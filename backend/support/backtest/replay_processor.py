import asyncio
import aiohttp
import time
from pathlib import Path
from typing import Dict, List, Optional
from support.backtest.signal_recorder import recorder

class ReplayProcessor:
    """
    Handles data replay from Sierra Chart (DTC or CSV).
    In replay mode, signals are recorded to CSV instead of being sent to live MT5.
    """
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.is_replaying = False

    async def run_replay_session(self, symbol: str = "XAUUSD", tfs: List[str] = ["H1", "M15", "M5"]):
        """
        Polls the Data Feed Server for replayed bars and triggers the Strategy Manager.
        """
        print(f"[Replay] Starting Replay Session for {symbol}...")
        self.is_replaying = True
        
        # In a real replay, we might want to clear the recorder first
        recorder.clear()
        
        async with aiohttp.ClientSession() as session:
            while self.is_replaying:
                try:
                    # 1. Fetch latest replayed data from API
                    # Note: In replay, the API serves the data as if it were live
                    # but we can detect it via a 'replay_mode' flag in the response or settings.
                    
                    # For this implementation, we assume the user is running Sierra in Replay mode
                    # and the Data Feed Server is relaying that data.
                    
                    # We will simulate a faster-than-light loop for backtesting
                    # OR wait for the user to trigger bars in Sierra.
                    
                    # Since we are in the Python Engine, we just need to know if we are in REPLAY mode
                    # to toggle 'record_only' in the bridge.
                    
                    await asyncio.sleep(1) # Replay tick interval
                    
                except Exception as e:
                    print(f"[Replay] Error: {e}")
                    await asyncio.sleep(5)

    def stop_replay(self):
        self.is_replaying = False
        print("[Replay] Session stopped.")

# Implementation Note:
# The actual logic for "Replay Mode" will be integrated into main_loop.py
# by checking an ENV variable or a CLI flag.
