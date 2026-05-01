import asyncio
import aiohttp
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from support.strategies.filter_one import FilterOne
from support.strategies.filter_two import FilterTwo
from support.strategies.orderflow import OrderflowStrategy
from support.strategies.manager import StrategyManager

async def diag_confluence():
    print("--- Institutional Trading System: Strategy Confluence Diag ---")
    API_URL = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch Data
        try:
            async with session.get(f"{API_URL}/ohlc?tf=H1&limit=500") as resp:
                h1_data = await resp.json()
            async with session.get(f"{API_URL}/ohlc?tf=M15&limit=500") as resp:
                m15_data = await resp.json()
            async with session.get(f"{API_URL}/ohlc?tf=M5&limit=500") as resp:
                m5_data = await resp.json()
            async with session.get(f"{API_URL}/delta?tf=M5&limit=500") as resp:
                delta_struct = await resp.json()
        except Exception as e:
            print(f"[FATAL] Data Fetch Error: {e}")
            return

        h1 = h1_data.get("candles", [])
        m15 = m15_data.get("candles", [])
        m5 = m5_data.get("candles", [])

        print(f"Data Status: H1({len(h1)}), M15({len(m15)}), M5({len(m5)}), Delta({len(delta_struct.get('delta', []))})")

        # 2. Evaluate Filters
        f1 = FilterOne()
        f2 = FilterTwo()
        of = OrderflowStrategy()
        
        f1_res = f1.evaluate(h1, m15, m5)
        f2_res = f2.evaluate(h1, m15, m5)
        
        # Inject zone for Orderflow
        kwargs = {"delta_struct": delta_struct}
        if f2_res and "active_zone" in f2_res:
            kwargs["active_zone"] = f2_res["active_zone"]
        
        of_res = of.evaluate(h1, m15, m5, **kwargs)

        print("\n--- Confluence Report ---")
        print(f"Filter 1 (H1 Bias):  {f1_res['action'] if f1_res else 'RANGE/NONE'} | {f1_res['desc'] if f1_res else 'No Bias Detected'}")
        print(f"Filter 2 (M15 Zone): {f2_res['action'] if f2_res else 'NONE'} | {f2_res['desc'] if f2_res else 'Price NOT in any Zone'}")
        print(f"Trigger (M5 Delta): {of_res['action'] if of_res else 'NONE'} | {of_res['desc'] if of_res else 'No Flip/Surge Detected'}")

        if f1_res and f2_res and of_res:
            if f1_res["action"] == f2_res["action"] == of_res["action"]:
                 print("\n[!!!] CONFLUENCE ACHIEVED - SIGNAL SHOULD BE ACTIVE")
            else:
                 print("\n[WAIT] Filters met but directions MISALIGNED.")
        else:
             print("\n[WAIT] Missing one or more filters for a valid signal.")

if __name__ == "__main__":
    asyncio.run(diag_confluence())
