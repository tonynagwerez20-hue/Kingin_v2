import pandas as pd
import sys
from pathlib import Path
import os
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from support.strategies.filter_one import FilterOne
from support.strategies.filter_two import FilterTwo
from support.strategies.candlestick_trigger import CandlestickStrategy
from support.risk.risk_calculator import RiskCalculator
from support.risk.cro_rules import CRORules

# ============================================================================
# DATA LOADING
# ============================================================================

def load_sierra_csv(path):
    if not os.path.exists(path):
        print(f"[Error] File not found: {path}")
        return None
    
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

# ============================================================================
# MAIN SIGNAL GENERATION
# ============================================================================

def run_signal_generator():
    print("=== Multi-Timeframe Signal Generator ===")
    print("Filters: FilterOne + FilterTwo + Candlestick Trigger")
    print("Parameters: SL=150 pips, TP=300 pips\n")
    
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
    
    # Initialize filters
    f1 = FilterOne()
    f2 = FilterTwo()
    cs = CandlestickStrategy()
    
    # Initialize Risk & Audit tools
    # Using $100 balance as requested
    risk_calc = RiskCalculator(account_balance=100.0, risk_percent=0.001)
    cro = CRORules(max_spread_pips=5.0) 
    
    signals_file = os.path.join(PROJECT_ROOT, "data", "backtest_signals.csv")
    
    # Clear existing file and write header
    with open(signals_file, "w") as f:
        f.write("timestamp,symbol,action,price,sl,tp,lots,description,magic\n")
    
    # Start loop
    m5_timestamps = df_m5['timestamp'].tolist()
    
    print(f"\n[2] Walking through {len(m5_timestamps)} M5 bars...")
    print(f"    Applying: FilterOne + FilterTwo + Candlestick Trigger\n")
    
    signals_count = 0
    rejected_stats = {
        "filter_one": 0,
        "filter_two": 0,
        "alignment": 0,
        "candlestick": 0,
        "cro_audit": 0
    }
    
    for idx, ts in enumerate(m5_timestamps):
        # Progress indicator
        if idx % 500 == 0:
            print(f"    Processing bar {idx}/{len(m5_timestamps)} ({signals_count} signals so far)...")
        
        # Get buffers
        h1_buf = get_buffer_at(df_h1, ts, limit=50)
        m15_buf = get_buffer_at(df_m15, ts, limit=50)
        m5_buf = get_buffer_at(df_m5, ts, limit=50)
        
        if len(h1_buf) < 10 or len(m15_buf) < 10 or len(m5_buf) < 10:
            continue
        
        # 1. Evaluate Trigger First (Candlestick Pattern)
        cs_res = cs.evaluate(h1_buf, m15_buf, m5_buf)
        if not cs_res:
            continue
            
        # Trigger found! Now apply filters
        trigger_action = cs_res["action"]
        dt = datetime.fromtimestamp(ts)
        dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        price = m5_buf[-1]["close"]
        desc = cs_res.get('desc', f'Trigger: {trigger_action}')
        
        # 2. Microstructure Audit (CRO Rules)
        market_data = {
            "spread": 2.0,  # Sierra data fallback, assume 2.0 pips for Gold
            "volume": m5_buf[-1].get("volume", 0)
        }
        audit_res = cro.audit_trade_request({}, market_data)

        # 3. FILTER 1: FilterOne (Confluence/Bias)
        f1_res = f1.evaluate(h1_buf, m15_buf, m5_buf)
        
        status = "UNKNOWN"
        reason = "PENDING"
        active_zone = None
        
        if audit_res["status"] == "FAIL":
            # VETOED BY CRO
            status = "VETO_CRO"
            reason = audit_res["reason"]
            rejected_stats["cro_audit"] += 1
        elif not f1_res or f1_res["action"] != trigger_action:
            # VETOED BY F1
            status = "VETO_F1"
            reason = "HTF Bias mismatch"
            rejected_stats["filter_one"] += 1
        else:
            # 4. FILTER 2: FilterTwo (Zones)
            kwargs = {"active_zone": f1_res.get("active_zone")}
            f2_res = f2.evaluate(h1_buf, m15_buf, m5_buf, **kwargs)
            if not f2_res or f2_res["action"] != trigger_action:
                # VETOED BY F2
                status = "VETO_F2"
                reason = "Not in Supply/Demand Zone"
                rejected_stats["filter_two"] += 1
            else:
                # ALL PASSED
                status = trigger_action
                reason = "PASSED ALL FILTERS"
                signals_count += 1
                active_zone = f2_res.get("active_zone")
        
        # 5. RISK CALCULATION (Dynamic SL/Lots)
        risk_params = risk_calc.calculate_trade_params(trigger_action, price, active_zone)
        sl = risk_params["sl"]
        lots = risk_params["lots"]
        
        # TP Calculation (Backtest standard: 3x risk)
        tp_pips = risk_params["sl_pips"] * 3.0
        if trigger_action == "LONG":
            tp = price + (tp_pips / 10)
        else:
            tp = price - (tp_pips / 10)
            
        # Final description enhancement
        final_desc = f"[{reason}] {desc} | SL_PIPS: {risk_params['sl_pips']}"
        
        # Write to CSV
        signal_line = f"{dt_str},XAUUSD,{status},{price:.2f},{sl:.2f},{tp:.2f},{lots:.2f},\"{final_desc}\",654321\n"
        
        with open(signals_file, "a") as f:
            f.write(signal_line)
            
        if status in ["LONG", "SHORT"]:
            print(f"[{dt_str}] SIGNAL: {status} @ {price:.2f} | {reason}")
        else:
            # Only print vetoes periodically to avoid spam
            if idx % 50 == 0:
                print(f"   (Vetoed) [{dt_str}] {trigger_action} @ {price:.2f} | Reason: {reason}")

    print(f"\n[3] Signal Generation Complete!")
    print(f"    Total Signals: {signals_count}")
    print(f"    Output: {signals_file}")
    
    print(f"\n[4] Rejection Statistics:")
    total_rejected = sum(rejected_stats.values())
    for reason, count in rejected_stats.items():
        pct = (count / len(m5_timestamps)) * 100 if len(m5_timestamps) > 0 else 0
        print(f"    {reason.replace('_', ' ').title()}: {count} ({pct:.1f}%)")
    
    print(f"\n[5] Summary:")
    print(f"    Total M5 Bars: {len(m5_timestamps)}")
    print(f"    Total Rejected: {total_rejected}")
    print(f"    Total Accepted: {signals_count}")
    print(f"    Acceptance Rate: {(signals_count / len(m5_timestamps)) * 100:.2f}%")

if __name__ == "__main__":
    run_signal_generator()
