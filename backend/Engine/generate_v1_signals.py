import pandas as pd
import sys
from pathlib import Path
import os
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from Engine.igof.v1_engine import V1FiltrationEngine
from support.price_action.supply_and_demand import detect_supply_demand
from support.risk.cro_rules import CRORules

def load_sierra_csv(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, skipinitialspace=True)
    df['dt_str'] = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
    df['timestamp'] = pd.to_datetime(df['dt_str']).apply(lambda x: int(x.timestamp()))
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Last': 'close', 'Volume': 'volume'})
    return df.sort_values('timestamp')

def run_generator():
    print("=== Upgraded Signal Generator: V1 Filtration Engine ===")
    
    h1_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_H1.txt")
    m5_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_M5.txt")
    
    print("[1] Loading Data...")
    df_h1 = load_sierra_csv(h1_path)
    df_m5 = load_sierra_csv(m5_path)
    
    if df_h1 is None or df_m5 is None:
        print("[Error] Missing data files.")
        return

    engine = V1FiltrationEngine()
    cro = CRORules(max_spread_pips=3.0)
    signals_file = os.path.join(PROJECT_ROOT, "data", "backtest_signals.csv")
    
    with open(signals_file, "w") as f:
        f.write("Time,Symbol,Action,Price,SL,TP,Lots,Description,Magic\n")

    m5_data = df_m5.to_dict('records')
    h1_data = df_h1.to_dict('records')
    
    print(f"[2] Processing {len(m5_data)} bars...")
    
    count = 0
    last_h1_ts = None
    cached_zones = []
    
    # Pre-calculate H1 buffers for each M5 bar to avoid repetitive slicing
    # For speed, we'll find the H1 index for each M5 bar
    h1_idx = 0
    
    for i in range(50, len(m5_data)):
        m5_bar = m5_data[i]
        ts = m5_bar['timestamp']
        
        # Advance H1 index to keep up with M5 timestamp
        # h1_data[h1_idx] is the H1 bar ending at or before M5
        while h1_idx < len(h1_data) - 1 and h1_data[h1_idx+1]['timestamp'] <= ts:
            h1_idx += 1
            
        if h1_idx < 10: continue
        
        h1_buf = h1_data[max(0, h1_idx-49):h1_idx+1]
        m5_buf = m5_data[i-49:i+1]
        
        # Detect zones once per H1 bar
        if h1_buf[-1]['timestamp'] != last_h1_ts:
            cached_zones = detect_supply_demand(df_h1.iloc[max(0, h1_idx-49):h1_idx+1])
            last_h1_ts = h1_buf[-1]['timestamp']
            
        snapshot = {
            "h1_candles": h1_buf,
            "m5_candles": m5_buf,
            "active_zone": cached_zones[-1] if cached_zones else None,
            "price": m5_bar['close']
        }
        
        res = engine.process_all_layers(snapshot)
        
        # --- CRO RULE AUDIT ---
        # Simulate realistic spread for backtest validation (1.2 to 2.8 pips)
        import random
        sim_spread = round(random.uniform(1.2, 2.8), 2)
        market_data = {
            "spread": sim_spread,
            "volume": m5_bar['volume']
        }
        cro_res = cro.audit_trade_request({}, market_data)
        
        if res["action"] == "TRADE_ALLOWED" and cro_res["status"] == "PASS":
            # Determine direction from H1 Bias Logic
            # L1 logic: Bullish FVG or BOS High = LONG
            # Since calculate_h1_bias sets self.h1_bias_score
            # We can check specific bias
            bias_score = res.get("bias", 0)
            
            # Simple directional proxy: Last H1 close vs open
            direction = "LONG" if h1_buf[-1]['close'] > h1_buf[-1]['open'] else "SHORT"
            
            dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            sl = m5_bar['close'] - 5.0 if direction == "LONG" else m5_bar['close'] + 5.0
            
            desc = f"V1-Pass | Bias:{bias_score} | {res['reason']}"
            # 9 Columns: Time,Symbol,Action,Price,SL,TP,Lots,Description,Magic
            f_line = f"{dt_str},XAUUSD,{direction},{m5_bar['close']:.2f},{sl:.2f},0.0,0.1,{desc},654321\n"
            
            with open(signals_file, "a") as f:
                f.write(f_line)
            
            count += 1
            if count % 10 == 0:
                print(f"  Generated {count} signals...")

    print(f"[3] Complete. Total signals: {count}")
    print(f"    Saved to: {signals_file}")

if __name__ == "__main__":
    run_generator()
