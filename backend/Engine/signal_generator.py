import asyncio
import sys
from pathlib import Path
import pandas as pd
import time
import importlib.util

# ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Fix for "networking" directory
try:
    from networking.dispatcher import DataDispatcher, delta_buffers
    from networking.server import build_delta_struct
except ImportError:
    # Check if we need to look in networking if the root import fails
    networking_path = project_root / "networking"
    sys.path.append(str(networking_path))
    from dispatcher import DataDispatcher, delta_buffers
    from server import build_delta_struct


try:
    from support.price_action.bias import calculate_structure_bias
    from support.price_action.supply_and_demand import detect_supply_demand
    from support.price_action.candlestick_patterns import get_candlestick_signal, recognize_patterns
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Import shared Aggregator state if possible, or assume API
try:
    from core.Aggregator import ohlc_buffers
except ImportError:
    ohlc_buffers = {}


# Import Bridge
try:
    from execution.bridge import Bridge
except ImportError:
    try:
        from bridge import Bridge
    except ImportError:
        print("Warning: Could not import Bridge. MQL5 signals will not be sent.")
        Bridge = None

async def main():
    print("Starting Signal Generator...")
    import aiohttp
    
    # Initialize Bridge
    bridge = None
    if Bridge:
        try:
            bridge = Bridge(port=5555)
        except Exception as e:
            print(f"Bridge init error: {e}")
    
    API_URL = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # 1. Get H1 Data for Bias
                async with session.get(f"{API_URL}/ohlc?tf=H1&limit=50") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        h1_candles = data.get("candles", [])
                        if h1_candles:
                            ohlc_buffers["H1"] = h1_candles 

                # 2. Get M15 Data for Zones
                async with session.get(f"{API_URL}/ohlc?tf=M15&limit=50") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        m15_candles = data.get("candles", [])
                        if m15_candles:
                            ohlc_buffers["M15"] = m15_candles

                # 3. Calculate Bias (H1)
                bias = calculate_structure_bias("H1")
                
                # 4. Calculate Zones (M15)
                if m15_candles:
                    df_m15 = pd.DataFrame(m15_candles)
                    zones = detect_supply_demand(df_m15) or []
                else:
                    zones = []
                
                # 5. Get Candlestick Signal (M5)
                candlestick_signal = get_candlestick_signal(ltf_candles)
                patterns = recognize_patterns(ltf_candles)
                
                # 6. Logic
                current_price = ltf_candles[-1]["close"] if ltf_candles else 0
                
                in_demand = False
                in_supply = False
                
                for z in zones:
                    if z["type"] == "demand" and z["low"] <= current_price <= z["high"]:
                        in_demand = True
                    if z["type"] == "supply" and z["low"] <= current_price <= z["high"]:
                        in_supply = True
                
                signal = "WAIT"
                
                # LONG: Bias Bullish + In Demand + Bullish Candle Pattern
                if in_demand and bias == "BULLISH" and candlestick_signal == "BUY":
                    signal = "LONG"
                    
                # SHORT: Bias Bearish + In Supply + Bearish Candle Pattern
                elif in_supply and bias == "BEARISH" and candlestick_signal == "SELL":
                    signal = "SHORT"
                    
                print(f"Bias: {bias} | InZone: {in_demand or in_supply} | Patterns: {', '.join(patterns) if patterns else 'None'} | Signal: {signal}")
                
                # Send to Bridge
                if signal != "WAIT" and bridge:
                    bridge.send_signal({
                        "action": signal,
                        "symbol": "XAUUSD",
                        "price": current_price,
                        "bias": bias,
                        "patterns": patterns
                    })
                
            except Exception as e:
                print(f"Error loop: {e}")
                
            await asyncio.sleep(5) # Poll every 5s

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
