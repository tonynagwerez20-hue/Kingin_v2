import pandas as pd
import sys
from pathlib import Path
import os
from datetime import datetime
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from Engine.igof.v1_engine import V1FiltrationEngine
from support.price_action.supply_and_demand import detect_supply_demand

def load_sierra_csv(path):
    if not os.path.exists(path):
        print(f"[Error] File not found: {path}")
        return None
    
    df = pd.read_csv(path, skipinitialspace=True)
    df['dt_str'] = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
    
    # Handle Sierra format
    try:
        df['dt'] = pd.to_datetime(df['dt_str'])
        df['timestamp'] = df['dt'].apply(lambda x: int(x.timestamp()))
    except Exception as e:
        print(f"[Error] Datetime parsing failed: {e}")
        return None
        
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Last': 'close',
        'Volume': 'volume'
    })
    return df.sort_values('timestamp')

def run_isignal_generator():
    print("=== IG-Signals: Forensic Backtest Data Generator ===")
    
    h1_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_H1.txt")
    m5_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_M5.txt")
    output_file = os.path.join(PROJECT_ROOT, "data", "isignals_backtest.csv")
    
    print(f"[1] Loading Data Files...")
    df_h1 = load_sierra_csv(h1_path)
    df_m5 = load_sierra_csv(m5_path)
    
    if df_h1 is None or df_m5 is None:
        print("[Abort] Missing source data.")
        return

    # Initialize Engine (Default Modular Layers)
    engine = V1FiltrationEngine()
    
    # Prepare CSV Header
    header = "Time,Price,L0_Session,L1_Bias,L2_Zone,L3_Liq,L4_mBOS,L5_Disp,Final_Action,Reason\n"
    with open(output_file, "w") as f:
        f.write(header)
    
    m5_data = df_m5.to_dict('records')
    h1_data = df_h1.to_dict('records')
    
    print(f"[2] Processing {len(m5_data)} iterations...")
    
    h1_idx = 0
    last_h1_ts = None
    cached_zones = []
    log_count = 0
    
    for i in range(50, len(m5_data)):
        m5_bar = m5_data[i]
        ts = m5_bar['timestamp']
        
        # Advance H1 buffer
        while h1_idx < len(h1_data) - 1 and h1_data[h1_idx+1]['timestamp'] <= ts:
            h1_idx += 1
        
        if h1_idx < 10: continue
        
        h1_buf = h1_data[max(0, h1_idx-49):h1_idx+1]
        m5_buf = m5_data[i-49:i+1]
        
        # Dynamic Zone Detection
        if h1_buf[-1]['timestamp'] != last_h1_ts:
            # Simple zone proxy for backtest speed
            cached_zones = detect_supply_demand(pd.DataFrame(h1_buf))
            last_h1_ts = h1_buf[-1]['timestamp']
            
        snapshot = {
            "h1_candles": h1_buf,
            "m5_candles": m5_buf,
            "active_zone": cached_zones[-1] if cached_zones else None,
            "current_time": ts,
            "price": m5_bar['close']
        }
        
        # Run Modular Engine
        res = engine.process_all_layers(snapshot)
        
        # Extract individual layer results
        # layer_results is a list of dicts: {"status": bool, "reason": str, ...}
        layer_res = res.get("layer_results", [])
        
        # Mapping: 0=Session, 1=H1Bias, 2=Zone, 3=Liq, 4=mBOS, 5=Disp
        # We ensure we have enough results, otherwise use "N/A"
        l_stat = []
        for j in range(6):
            if j < len(layer_res):
                l_stat.append("PASS" if layer_res[j]["status"] else "FAIL")
            else:
                l_stat.append("SKIP")
        
        dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        row = f"{dt_str},{m5_bar['close']:.2f},{l_stat[0]},{l_stat[1]},{l_stat[2]},{l_stat[3]},{l_stat[4]},{l_stat[5]},{res['action']},{res['reason'].replace(',', '|')}\n"
        
        with open(output_file, "a") as f:
            f.write(row)
            
        log_count += 1
        if log_count % 500 == 0:
            print(f"  > Logged {log_count} forensic rows...")

    print(f"\n[3] iSignal Generation Complete.")
    print(f"    Exported: {output_file}")
    print(f"    Forensic Density: {log_count} rows")

if __name__ == "__main__":
    run_isignal_generator()
