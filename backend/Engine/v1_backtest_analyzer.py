import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

def load_sierra_csv(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, skipinitialspace=True)
    df['dt_str'] = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
    df['timestamp'] = pd.to_datetime(df['dt_str']).apply(lambda x: int(x.timestamp()))
    df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Last': 'close', 'Volume': 'volume'})
    return df.sort_values('timestamp')

def run_analysis():
    print("=== V1 Backtest Analyzer: Upgraded Signal Performance ===")
    
    signals_path = os.path.join(PROJECT_ROOT, "data", "backtest_signals.csv")
    m5_path = os.path.join(PROJECT_ROOT, "data_feed", "sierra_M5.txt")
    
    if not os.path.exists(signals_path):
        print(f"[Error] Signals file not found: {signals_path}")
        return

    print("[1] Loading Data...")
    df_signals = pd.read_csv(signals_path)
    df_m5 = load_sierra_csv(m5_path)
    
    if df_m5 is None:
        print("[Error] M5 data file not found.")
        return

    m5_data = df_m5.to_dict('records')
    m5_lookup = {r['timestamp']: i for i, r in enumerate(m5_data)}
    
    results = []
    # EA Constraints
    DAILY_DD_LIMIT = 0.025 # 2.5%
    TRAILING_PIPS = 20.0
    TRAILING_STEP = 5.0
    
    balance = 10000.0  # Starting balance
    daily_start_balance = balance
    current_day = None
    equity_curve = [balance]
    
    print(f"[2] Simulating {len(df_signals)} signals with EA-Logic (Trailing SL & Daily DD)...")
    
    for idx, sig in df_signals.iterrows():
        sig_time = pd.to_datetime(sig['Time'])
        
        # Daily Reset & Drawdown Check
        if current_day is None or sig_time.date() != current_day:
            current_day = sig_time.date()
            daily_start_balance = balance
            
        if (daily_start_balance - balance) / daily_start_balance > DAILY_DD_LIMIT:
            continue # Blocked by EA Daily Drawdown limit
            
        try:
            sig_ts = int(sig_time.timestamp())
            start_price = float(sig['Price'])
            initial_sl = float(sig['SL'])
            direction = sig['Action']
            
            # Risk/Reward 1:3 for TP
            risk = abs(start_price - initial_sl)
            tp = start_price + (risk * 3.0) if direction == "LONG" else start_price - (risk * 3.0)
            
            current_sl = initial_sl
            
            # Find starting bar
            if sig_ts not in m5_lookup:
                # Find nearest future bar
                valid_m5 = df_m5[df_m5['timestamp'] >= sig_ts]
                if valid_m5.empty: continue
                m5_idx = m5_lookup[valid_m5.iloc[0]['timestamp']]
            else:
                m5_idx = m5_lookup[sig_ts]
            
            outcome = "OPEN"
            exit_price = 0
            
            for i in range(m5_idx, len(m5_data)):
                bar = m5_data[i]
                
                # 1. Update Trailing Stop (EA Logic)
                if direction == "LONG":
                    # If price moved in our favor by TRAILING_PIPS + STEP
                    if bar['high'] > start_price + (TRAILING_PIPS/10.0):
                        new_sl = bar['high'] - (TRAILING_PIPS/10.0)
                        if new_sl > current_sl + (TRAILING_STEP/10.0):
                            current_sl = new_sl
                            
                    # Check Exit
                    if bar['high'] >= tp:
                        outcome = "WIN"
                        exit_price = tp
                        break
                    elif bar['low'] <= current_sl:
                        outcome = "LOSS"
                        exit_price = current_sl
                        break
                else: # SHORT
                    if bar['low'] < start_price - (TRAILING_PIPS/10.0):
                        new_sl = bar['low'] + (TRAILING_PIPS/10.0)
                        if new_sl < current_sl - (TRAILING_STEP/10.0):
                            current_sl = new_sl
                            
                    # Check Exit
                    if bar['low'] <= tp:
                        outcome = "WIN"
                        exit_price = tp
                        break
                    elif bar['high'] >= current_sl:
                        outcome = "LOSS"
                        exit_price = current_sl
                        break
            
            if outcome != "OPEN":
                pnl = (exit_price - start_price) if direction == "LONG" else (start_price - exit_price)
                pnl_dollars = pnl * 10 
                
                balance += pnl_dollars
                equity_curve.append(balance)
                
                results.append({
                    "time": sig['Time'],
                    "action": direction,
                    "entry": start_price,
                    "exit": exit_price,
                    "outcome": outcome,
                    "pnl_dollars": pnl_dollars,
                    "balance": balance
                })
        except Exception as e:
            print(f"Error processing signal {idx}: {e}")

    # --- REPORTING ---
    df_results = pd.DataFrame(results)
    if df_results.empty:
        print("[Error] No signals were executed in simulation.")
        return

    win_rate = (df_results['outcome'] == "WIN").mean() * 100
    total_pnl = df_results['pnl_dollars'].sum()
    max_dd = (pd.Series(equity_curve).cummax() - pd.Series(equity_curve)).max()
    
    print("\n" + "="*50)
    print("BACKTEST RESULTS (V1 FILTRATION)")
    print("="*50)
    print(f"Total Signals:  {len(df_signals)}")
    print(f"Executed:       {len(df_results)}")
    print(f"Win Rate:       {win_rate:.2f}%")
    print(f"Total Profit:  ${total_pnl:,.2f}")
    print(f"Max Drawdown:  ${max_dd:,.2f}")
    print(f"Profit Factor: {abs(df_results[df_results['pnl_dollars'] > 0]['pnl_dollars'].sum() / (df_results[df_results['pnl_dollars'] < 0]['pnl_dollars'].sum() or 1)):.2f}")
    print("="*50)
    
    # Save results
    report_csv = os.path.join(PROJECT_ROOT, "data", "v1_backtest_report.csv")
    df_results.to_csv(report_csv, index=False)
    
    # Plot equity curve
    plt.figure(figsize=(10, 6))
    plt.plot(equity_curve, color='green', linewidth=2)
    plt.title("Upgraded Filtration System: Equity Curve (1:3 RR)")
    plt.xlabel("Trade Number")
    plt.ylabel("Account Balance ($)")
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PROJECT_ROOT, "data", "v1_equity_curve.png"))
    plt.close()
    
    print(f"\n[3] Reports Generated:")
    print(f"    - CSV:  {report_csv}")
    print(f"    - Plot: {os.path.join(PROJECT_ROOT, 'data', 'v1_equity_curve.png')}")

if __name__ == "__main__":
    run_analysis()
