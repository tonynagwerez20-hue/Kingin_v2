import pandas as pd
import sys
from pathlib import Path
import os
from datetime import datetime
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from support.strategies.filter_one import FilterOne
from support.strategies.filter_two import FilterTwo
from support.strategies.orderflow import OrderflowStrategy
from Engine.igof.stack import FiltrationController

def load_sierra_csv(path):
    if not os.path.exists(path):
        print(f"[Error] File not found: {path}")
        return None
    
    # Header: Date, Time, Open, High, Low, Last, Volume, # of Trades, OHLC Avg, HLC Avg, HL Avg, Bid Volume, Ask Volume
    # Index 11 = Bid Volume, Index 12 = Ask Volume
    df = pd.read_csv(path, skipinitialspace=True)
    
    # Combine Date & Time
    df['dt_str'] = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
    df['timestamp'] = pd.to_datetime(df['dt_str']).apply(lambda x: int(x.timestamp()))
    
    # Rename columns to standard internal format
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Last': 'close',
        'Volume': 'volume'
    })
    
    # Calculate Delta if Bid/Ask Volume exists
    if 'Bid Volume' in df.columns and 'Ask Volume' in df.columns:
        df['delta'] = df['Ask Volume'] - df['Bid Volume']
    else:
        df['delta'] = 0.0
        
    return df.sort_values('timestamp')

def get_buffer_at(df, target_ts, limit=50):
    """Returns a list of dicts representing candles completed before or at target_ts."""
    mask = df['timestamp'] <= target_ts
    subset = df[mask].tail(limit)
    return subset[['open', 'high', 'low', 'close', 'volume', 'delta', 'timestamp']].to_dict('records')

def run_backtest():
    print("=== Institutional Trading System: Historical Backtest Engine ===")
    
    h1_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_H1.txt")
    m15_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_M15.txt")
    m5_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_M5.txt")
    
    print(f"[1] Loading Data...")
    df_h1 = load_sierra_csv(h1_path)
    df_m15 = load_sierra_csv(m15_path)
    df_m5 = load_sierra_csv(m5_path)
    
    if df_h1 is None or df_m15 is None or df_m5 is None:
        return

    print(f"    H1: {len(df_h1)} bars")
    print(f"    M15: {len(df_m15)} bars")
    print(f"    M5: {len(df_m5)} bars")
    
    # Shared objects
    f1 = FilterOne()
    f2 = FilterTwo()
    of = OrderflowStrategy()
    filtration = FiltrationController()
    
    signals_file = os.path.join(PROJECT_ROOT, "data", "backtest_signals.csv")
    
    # Clear signals file
    with open(signals_file, "w") as f:
        f.write("Time,Symbol,Action,Price,SL,Lots,Description,Magic\n")
    
    # Start loop from where we have enough data (e.g. at least 50 bars in each)
    # We iterate over the M5 timestamps
    m5_timestamps = df_m5['timestamp'].tolist()
    
    print(f"\n[2] Walking through {len(m5_timestamps)} M5 bars with IGOF V1 Active...")
    
    signals_count = 0
    last_h1_ts = None
    cached_zones = []
    
    for ts in m5_timestamps:
        # Get buffers as they were at this timestamp
        h1_buf = get_buffer_at(df_h1, ts, limit=50)
        m15_buf = get_buffer_at(df_m15, ts, limit=50)
        m5_buf = get_buffer_at(df_m5, ts, limit=50)
        
        if len(h1_buf) < 10 or len(m15_buf) < 10 or len(m5_buf) < 10:
            continue
            
        # Optimization: Only re-detect zones if H1 candle closed
        current_h1_ts = h1_buf[-1]['timestamp']
        if current_h1_ts != last_h1_ts:
            from support.price_action.supply_and_demand import detect_supply_demand
            cached_zones = detect_supply_demand(pd.DataFrame(h1_buf))
            last_h1_ts = current_h1_ts

        igof_snapshot = {
            "h1_candles": h1_buf,
            "m5_candles": m5_buf,
            "active_zone": cached_zones[-1] if cached_zones else None,
            "price": m5_buf[-1]["close"],
            "gc_m15": m15_buf, 
            "zn_m15": m15_buf,
            "6e_m15": m15_buf,
            "es_m15": m15_buf
        }
        
        igof_res = filtration.process(igof_snapshot)
        if igof_res["action"] == "NO_TRADE":
            continue

        # 1. Evaluate Confluence
        f1_res = f1.evaluate(h1_buf, m15_buf, m5_buf)
        f2_res = f2.evaluate(h1_buf, m15_buf, m5_buf)
        
        if not f1_res or not f2_res:
            continue
            
        if f1_res["action"] != f2_res["action"]:
            continue
            
        # 2. Evaluate Orderflow
        # Strategy expects latest bar at index 0
        rev_m5 = list(reversed(m5_buf))
        
        deltas = [c['delta'] for c in rev_m5]
        max_deltas = [c.get('max_delta', c['delta']) for c in rev_m5]
        min_deltas = [c.get('min_delta', c['delta']) for c in rev_m5]
        
        # Calculate cumulative delta (rolling sum of the reversed list)
        cumulative = []
        s = 0.0
        for d in deltas:
            s += d
            cumulative.append(s)
            
        delta_struct = {
            "delta": deltas,
            "max": max_deltas,
            "min": min_deltas,
            "cumulative": cumulative
        }
        
        kwargs = {"delta_struct": delta_struct}
        if "active_zone" in f2_res:
            kwargs["active_zone"] = f2_res["active_zone"]
            
        of_res = of.evaluate(h1_buf, m15_buf, m5_buf, **kwargs)
        
        if of_res and of_res["action"] == f1_res["action"]:
            # SIGNAL GENERATED
            dt = datetime.fromtimestamp(ts)
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            price = m5_buf[-1]["close"]
            
            # SL is usually +/- 5.0 for Gold dummy, or logic-based
            sl = price - 5.0 if of_res["action"] == "LONG" else price + 5.0
            
            # Combine IGOF reason with description
            full_desc = f"IGOF: {igof_res.get('reason', 'PASS')} | {of_res['desc']}"
            signal_line = f"{dt_str},XAUUSD,{of_res['action']},{price:.2f},{sl:.2f},0.1,{full_desc},654321\n"
            
            with open(signals_file, "a") as f:
                f.write(signal_line)
                
            signals_count += 1
            print(f"[{dt_str}] SIGNAL: {of_res['action']} @ {price:.2f} | {igof_res['reason']}")

    print(f"\n[3] Backtest Complete. Total Signals: {signals_count}")
    print(f"    Results saved to: {signals_file}")

if __name__ == "__main__":
    run_backtest()
