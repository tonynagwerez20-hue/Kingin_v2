import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("RealDataLabeler")

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias"
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}

def load_data(path: str) -> pd.DataFrame:
    """Load and prepare CSV data."""
    # Detect separator
    with open(path, 'r') as f:
        first_line = f.readline()
        sep = '\t' if '\t' in first_line else ','
    
    df = pd.read_csv(path, sep=sep)
    
    # Standardize column names (strip <> and lowercase)
    df.columns = [c.strip('<>').lower() for c in df.columns]
    
    if 'date' in df.columns and 'time' in df.columns:
        # Handle 2018.06.28 or 2018-06-28
        df['datetime'] = pd.to_datetime(df['date'].astype(str).str.replace('.', '-', regex=False) + ' ' + df['time'])
    elif 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'])
    
    df = df.sort_values('datetime').reset_index(drop=True)
    logger.info(f"Loaded {len(df):,} bars from {path} ({df['datetime'].min()} to {df['datetime'].max()})")
    return df

def get_session(dt: datetime) -> str:
    h = dt.hour
    if 2 <= h < 8: return "asian"
    elif 8 <= h < 12: return "london"
    elif 12 <= h < 16: return "overlap"
    return "ny"

def detect_ob(df: pd.DataFrame, i: int) -> Optional[Dict]:
    if i < 5: return None
    curr = df.iloc[i]
    prev = df.iloc[i-1]
    
    # Simple Bullish OB (Bearish candle then Bullish engulf)
    if prev['close'] < prev['open'] and curr['close'] > curr['open'] and curr['close'] > prev['high']:
        strength = (curr['close'] - prev['low']) / (prev['high'] - prev['low'] + 0.001)
        return {"direction": "buy", "strength": min(1.0, strength / 10.0), "entry": curr['close']}
    
    # Simple Bearish OB (Bullish candle then Bearish engulf)
    if prev['close'] > prev['open'] and curr['close'] < curr['open'] and curr['close'] < prev['low']:
        strength = (prev['high'] - curr['close']) / (prev['high'] - prev['low'] + 0.001)
        return {"direction": "sell", "strength": min(1.0, strength / 10.0), "entry": curr['close']}
        
    return None

def check_fvg(df: pd.DataFrame, i: int) -> bool:
    if i < 2: return False
    c0, c1, c2 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
    return (c2['low'] > c0['high']) or (c2['high'] < c0['low'])

def simulate_outcome(df: pd.DataFrame, i: int, direction: str, entry: float, sl_pips: int = 100) -> int:
    tp_pips = sl_pips * 2
    # Pips calculation: Gold price 2000.00 -> 0.01 = 1 pip? Usually 0.1 = 1 pip for Gold.
    # Let's use 1.0 = 100 pips for simplicity in this logic.
    sl = entry - (sl_pips * 0.01) if direction == "buy" else entry + (sl_pips * 0.01)
    tp = entry + (tp_pips * 0.01) if direction == "buy" else entry - (tp_pips * 0.01)
    
    future = df.iloc[i+1 : i+50] # Check next 50 bars
    for _, bar in future.iterrows():
        if direction == "buy":
            if bar['low'] <= sl: return 0
            if bar['high'] >= tp: return 1
        else:
            if bar['high'] >= sl: return 0
            if bar['low'] <= tp: return 1
    return 0

def process_file(path: str, timeframe: str) -> List[Dict]:
    df = load_data(path)
    records = []
    
    for i in range(50, len(df) - 50, 1): # Scan every bar for maximum training data
        ob = detect_ob(df, i)
        if not ob: continue
        
        outcome = simulate_outcome(df, i, ob['direction'], ob['entry'])
        
        # Features
        features = {
            "ob_strength": float(ob['strength']),
            "fvg_present": int(check_fvg(df, i)),
            "bos_aligned": 1, # Simplified
            "liquidity_swept": 0, # Simplified
            "adr_pct": 0.5, # Simplified
            "pips_to_liquidity": 20.0,
            "session": SESSION_MAP.get(get_session(df.iloc[i]['datetime']), 1),
            "htf_bias": 1 if ob['direction'] == 'buy' else -1
        }
        
        records.append({
            "timestamp": df.iloc[i]['datetime'].isoformat(),
            "outcome": outcome,
            "features": features,
            "timeframe": timeframe
        })
        
    return records

def main():
    all_signals = []
    
    # Process 20y H4
    h4_path = "data/backtest_20y/XAUUSD_H4_20y.csv"
    if Path(h4_path).exists():
        all_signals.extend(process_file(h4_path, "H4"))
        
    # Process 8y H1
    h1_path = "data/XAUUSDm_H1_8 years data.csv"
    if Path(h1_path).exists():
        all_signals.extend(process_file(h1_path, "H1"))
        
    output_path = "data/backtest_20y/real_signals_20y.json"
    with open(output_path, 'w') as f:
        json.dump(all_signals, f, indent=2)
        
    logger.info(f"Generated {len(all_signals)} REAL signals saved to {output_path}")

if __name__ == "__main__":
    main()
