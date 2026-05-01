import pandas as pd
import sys
import os
import time
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from execution.bridge import Bridge

def replay_signals(file_path):
    print(f"=== Signal Replay Bridge: CSV -> MT5 EA ===")
    
    if not os.path.exists(file_path):
        print(f"[Error] Signals file not found: {file_path}")
        return

    # Initialize Bridge
    bridge = Bridge()
    if not bridge.connected:
        print("[Warning] Bridge initialized but MT5 EA not yet responding (check if MT5 is open).")

    # Load signals
    print(f"[1] Loading signals from {file_path}")
    df = pd.read_csv(file_path)
    
    print(f"[2] Replaying {len(df)} signals to EA...")
    
    for idx, row in df.iterrows():
        # Clean string values (Action, Symbol)
        action = row['Action'].strip()
        symbol = row['Symbol'].strip()

        # Construct signal dict expected by Bridge.send_signal
        # Expected by EA: {"action":..., "symbol":..., "price":..., "sl":..., "tp":..., "lots":..., "desc":..., "timestamp":...}
        signal = {
            "action": action,
            "symbol": symbol,
            "price": float(row['Price']),
            "sl": float(row['SL']),
            "tp": float(row['TP']) if 'TP' in row else 0.0,
            "lots": float(row['Lots']), 
            "desc": row['Description'],
            "magic": int(row['Magic'])
        }
        
        # Add timestamp if available
        if 'Time' in row:
            # Convert string time to timestamp (rough approximation or string pass-through depending on EA logic)
            # EA expects "timestamp" as long (epoch) or it parses string in ZMQ handler?
            # EA ParseSignal: timestamp = (long)NormalizeDouble(ExtractDoubleValue(json, "timestamp"), 0);
            # We need to send unix timestamp
            try:
                dt = pd.to_datetime(row['Time'])
                signal["timestamp"] = int(dt.timestamp())
            except:
                signal["timestamp"] = int(time.time())

        print(f"  [{idx+1}/{len(df)}] Sending {signal['action']} {signal['symbol']} @ {signal['price']}...")
        bridge.send_signal(signal)
        
        # Small delay to mimic live flow (optional, can be faster for bulk load)
        time.sleep(0.1)

    print(f"\n[3] Replay Complete.")
    bridge.close()

if __name__ == "__main__":
    # Point to the unified 9-column file
    signals_csv = os.path.join(PROJECT_ROOT, "data", "backtest_signals.csv")
    replay_signals(signals_csv)
