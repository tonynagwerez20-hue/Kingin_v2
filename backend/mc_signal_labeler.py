"""
MC SIGNAL LABELER
=============
Process 8-year XAUUSD historical data through the SMC strategy layers
to generate labeled training data for LightGBM ML model.

Key Innovation: Simulate realistic outcomes using actual future price action
(rather than assuming all signals win like the existing backtest).
"""

import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)
logger = logging.getLogger("MC_Labeler")

CONFIG = {
    "model_path": "models/lgbm_signal_filter.pkl",
    "trade_log_path": "data/trade_log.json",
    "hist_data_path": "data/XAUUSDm_H1_8 years data.csv",
    "lgbm_threshold": 0.62,
    "lgbm_retrain_days": 7,
    "lgbm_window_days": 120,
    "lgbm_min_samples": 30,
    "lgbm_params": {
        "objective": "binary",
        "metric": "binary_logloss",
        "n_estimators": 200,
        "max_depth": 5,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 20,
        "n_jobs": 1,
        "verbose": -1,
        "random_state": 42,
    },
    "drift_window": 30,
    "drift_acc_threshold": 0.45,
    "adwin_delta": 0.002,
    "confidence_step_up": 0.03,
    "confidence_floor": 0.50,
    "lgbm_weight": 0.70,
    "river_weight": 0.30,
    "base_risk_pct": 0.01,
    "max_risk_pct": 0.02,
    "min_risk_pct": 0.005,
    "pip_value_xauusd": 10.0,
    "tf_confluence_bonus": 0.04,
    "regime_window": 20,
    "regime_smooth": 3,
    "trending_threshold": 0.60,
    "choppy_range": 0.005,
    "choppy_bar": 0.001,
}

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias"
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}


def load_historical_data(path: str) -> pd.DataFrame:
    """Load the 8-year XAUUSD H1 data."""
    df = pd.read_csv(path, sep='\t')
    
    # Handle angle bracket column names (<DATE>, <TIME>, etc.)
    df.columns = [c.strip('<>').lower() for c in df.columns]
    
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df = df.sort_values('datetime').reset_index(drop=True)
    logger.info(f"Loaded {len(df):,} bars from {path}")
    logger.info(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    return df


def engineer_features(signal: dict) -> dict:
    """Convert SMC signal dict to ML feature vector."""
    return {
        "ob_strength": float(signal.get("ob_strength", 0.50)),
        "fvg_present": int(bool(signal.get("fvg_present", False))),
        "bos_aligned": int(bool(signal.get("bos_aligned", False))),
        "liquidity_swept": int(bool(signal.get("liquidity_swept", False))),
        "adr_pct": float(signal.get("adr_pct", 0.50)),
        "pips_to_liquidity": float(signal.get("pips_to_liquidity", 20.0)),
        "session": SESSION_MAP.get(signal.get("session", "london"), 1),
        "htf_bias": int(signal.get("htf_bias", 0)),
    }


def get_session(dt: datetime) -> str:
    """Determine trading session from datetime."""
    h = dt.hour
    if 2 <= h < 8:
        return "asian"
    elif 8 <= h < 12:
        return "london"
    elif 12 <= h < 16:
        return "overlap"
    return "ny"


def calculate_adr(df: pd.DataFrame, i: int, period: int = 24) -> float:
    """Calculate position within Average Daily Range (H1 bars)."""
    if i < period:
        return 0.5
    window = df.iloc[max(0, i-period):i]
    adr = (window['high'] - window['low']).mean()
    if adr <= 0:
        return 0.5
    pos = (df.iloc[i]['close'] - df.iloc[i]['low']) / adr
    return round(min(1.0, max(0.0, pos)), 4)


def calculate_liquidity_pips(df: pd.DataFrame, i: int, window: int = 20) -> float:
    """Calculate pips to nearest liquidity pool (recent swing high/low)."""
    if i < window:
        return 20.0
    subset = df.iloc[max(0, i-window):i]
    price = df.iloc[i]['close']
    swing_hi = subset['high'].max()
    swing_lo = subset['low'].min()
    dist_hi = abs(price - swing_hi) * 10
    dist_lo = abs(price - swing_lo) * 10
    return round(min(dist_hi, dist_lo), 1)


def get_htf_bias(df: pd.DataFrame, i: int, window: int = 50) -> int:
    """Get higher timeframe directional bias."""
    if i < window:
        return 0
    subset = df.iloc[max(0, i-window):i]['close']
    slope = subset.iloc[-1] - subset.iloc[0]
    if slope > 0:
        return 1
    elif slope < 0:
        return -1
    return 0


def detect_ob(df: pd.DataFrame, i: int, lookback: int = 10) -> Optional[Dict]:
    """
    Detect Order Block signature in recent candles.
    Simplified detection - looks for engulfing candle patterns.
    """
    if i < lookback + 2:
        return None
    
    window = df.iloc[max(0, i-lookback):i]
    current = df.iloc[i]
    
    # Look for bullish OB: bearish candle then bullish engulf
    for j in range(len(window) - 2, 0, -1):
        candle = window.iloc[j]
        prev = window.iloc[j-1] if j > 0 else None
        
        if prev is None:
            continue
            
        # Bullish engulfing
        if (prev['close'] < prev['open'] and 
            current['close'] > current['open'] and
            current['low'] < prev['low'] and
            current['high'] > prev['high']):
            
            ob_range = prev['high'] - prev['low']
            if ob_range <= 0:
                continue
                
            strength = min(1.0, ob_range / (df.iloc[i]['close'] * 0.002))
            
            return {
                "direction": "buy",
                "ob_strength": round(strength, 4),
                "fvg_present": True,
                "bos_aligned": True,
                "entry": current['close']
            }
    
    # Look for bearish OB: bullish candle then bearish engulf
    for j in range(len(window) - 2, 0, -1):
        candle = window.iloc[j]
        prev = window.iloc[j-1] if j > 0 else None
        
        if prev is None:
            continue
            
        # Bearish engulfing
        if (prev['close'] > prev['open'] and 
            current['close'] < current['open'] and
            current['high'] > prev['high'] and
            current['low'] < prev['low']):
            
            ob_range = prev['high'] - prev['low']
            if ob_range <= 0:
                continue
                
            strength = min(1.0, ob_range / (df.iloc[i]['close'] * 0.002))
            
            return {
                "direction": "sell",
                "ob_strength": round(strength, 4),
                "fvg_present": True,
                "bos_aligned": True,
                "entry": current['close']
            }
    
    return None


def check_fvg(df: pd.DataFrame, i: int) -> bool:
    """Check for Fair Value Gap (gap between candles)."""
    if i < 2:
        return False
    
    c0 = df.iloc[i-2]
    c1 = df.iloc[i-1]
    
    # Bullish FVG: gap up
    if c1['low'] > c0['high']:
        return True
    # Bearish FVG: gap down
    if c1['high'] < c0['low']:
        return True
    
    return False


def simulate_outcome(
    df: pd.DataFrame, 
    i: int, 
    direction: str, 
    entry: float, 
    sl_pips: float = 50,
    tp_rr: float = 2.0,
    max_bars: int = 48
) -> int:
    """
    Simulate trade outcome based on future price action.
    Returns: 1 = WIN (TP hit), 0 = LOSS (SL hit or timeout)
    """
    sl = entry - (sl_pips * 0.01) if direction == "buy" else entry + (sl_pips * 0.01)
    tp = entry + (sl_pips * tp_rr * 0.01) if direction == "buy" else entry - (sl_pips * tp_rr * 0.01)
    
    future = df.iloc[i+1:min(i+1+max_bars, len(df))]
    
    for _, bar in future.iterrows():
        if direction == "buy":
            if bar['low'] <= sl:
                return 0  # SL hit
            if bar['high'] >= tp:
                return 1  # TP hit
        else:
            if bar['high'] >= sl:
                return 0  # SL hit
            if bar['low'] <= tp:
                return 1  # TP hit
    
    return 0  # Timeout = loss (conservative)


def detect_regime(df: pd.DataFrame, i: int, window: int = 20) -> str:
    """Detect market regime (trending/ranging/choppy)."""
    if i < window + 5:
        return "unknown"
    
    closes = df.iloc[max(0, i-window):i]['close'].values
    diffs = np.diff(closes)
    
    up_moves = float(np.sum(diffs[diffs > 0]))
    dn_moves = float(abs(np.sum(diffs[diffs < 0])))
    total = up_moves + dn_moves
    
    if total == 0:
        return "unknown"
    
    direction_strength = abs(up_moves - dn_moves) / total
    
    if direction_strength > 0.60:
        return "trending"
    elif direction_strength < 0.30:
        return "choppy"
    else:
        return "ranging"


def scan_and_label(
    df: pd.DataFrame,
    sample_every: int = 10,
    min_lookback: int = 100,
    tp_rr: float = 2.0,
    sl_pips: int = 50
) -> List[Dict]:
    """
    Scan historical data, detect SMC signals, simulate outcomes,
    and return labeled training data.
    """
    records = []
    logger.info(f"Scanning {len(df):,} bars with sampling every {sample_every}...")
    
    for i in range(min_lookback, len(df) - 48):
        # Sample to avoid over-density
        if (i - min_lookback) % sample_every != 0:
            continue
        
        ob = detect_ob(df, i)
        if ob is None:
            continue
        
        dt = df.iloc[i]['datetime']
        
        # Get all signal features
        signal = {
            "ob_strength": ob["ob_strength"],
            "fvg_present": check_fvg(df, i),
            "bos_aligned": ob["bos_aligned"],
            "liquidity_swept": False,  # Simplified
            "adr_pct": calculate_adr(df, i),
            "pips_to_liquidity": calculate_liquidity_pips(df, i),
            "session": get_session(dt),
            "htf_bias": get_htf_bias(df, i),
            "direction": ob["direction"],
            "entry_price": ob["entry"],
            "sl_price": ob["entry"] - (sl_pips * 0.01) if ob["direction"] == "buy" else ob["entry"] + (sl_pips * 0.01),
            "tp_price": ob["entry"] + (sl_pips * tp_rr * 0.01) if ob["direction"] == "buy" else ob["entry"] - (sl_pips * tp_rr * 0.01),
            "regime": detect_regime(df, i),
        }
        
        # Simulate outcome
        outcome = simulate_outcome(
            df, i, ob["direction"], ob["entry"],
            sl_pips=sl_pips, tp_rr=tp_rr, max_bars=48
        )
        
        features = engineer_features(signal)
        
        records.append({
            "timestamp": dt.isoformat(),
            "signal": signal,
            "features": features,
            "confidence": 0.5,  # Will be scored by ML later
            "outcome": outcome,
            "metadata": {
                "source": "historical_labeler",
                "bar_index": i,
                "regime": signal["regime"]
            }
        })
        
        if len(records) % 500 == 0:
            logger.info(f"Progress: {len(records):,} signals labeled")
    
    return records


def save_trade_log(records: List[Dict], path: str):
    """Save labeled records to trade_log.json."""
    with open(path, 'w') as f:
        json.dump(records, f, indent=2, default=str)
    logger.info(f"Saved {len(records):,} records to {path}")


def load_trade_log(path: str) -> List[Dict]:
    """Load existing trade log."""
    if Path(path).exists():
        with open(path) as f:
            return json.load(f)
    return []


def merge_with_existing(new_records: List[Dict], existing_path: str) -> List[Dict]:
    """Merge new historical records with existing trade log."""
    existing = load_trade_log(existing_path)
    
    # Combine and remove duplicates based on timestamp
    combined = {r["timestamp"]: r for r in existing}
    combined.update({r["timestamp"]: r for r in new_records})
    
    merged = list(combined.values())
    logger.info(f"Merged: {len(existing)} existing + {len(new_records)} new = {len(merged)} total")
    return merged


def train_lightgbm(records: List[Dict], config: dict = CONFIG) -> bool:
    """Train LightGBM model on labeled data."""
    import lightgbm as lgb
    import joblib
    
    if len(records) < config["lgbm_min_samples"]:
        logger.warning(f"Insufficient data: {len(records)} < {config['lgbm_min_samples']}")
        return False
    
    # Prepare training data
    X = []
    y = []
    for r in records:
        feat = r.get("features", {})
        if all(k in feat for k in FEATURE_KEYS):
            X.append([feat[k] for k in FEATURE_KEYS])
            y.append(r.get("outcome", 0))
    
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=int)
    
    win_rate = y.mean()
    logger.info(f"Training LightGBM on {len(X)} samples, win_rate={win_rate:.1%}")
    
    # Train model
    model = lgb.LGBMClassifier(**config["lgbm_params"])
    model.fit(X, y)
    
    # Save model
    model_data = {
        "model": model,
        "trained_at": datetime.utcnow(),
        "train_samples": len(X),
        "train_win_rate": round(win_rate, 4)
    }
    joblib.dump(model_data, config["model_path"])
    
    # Feature importance
    importances = dict(zip(FEATURE_KEYS, model.feature_importances_))
    top = sorted(importances.items(), key=lambda x: -x[1])
    logger.info(f"LightGBM trained | samples={len(X)} win_rate={win_rate:.1%}")
    logger.info("Top features: " + " | ".join(f"{k}={v}" for k, v in top[:4]))
    
    return True


def main():
    print("\n" + "="*60)
    print("MC SIGNAL LABELER - 8-Year XAUUSD ML Training Data Generator")
    print("="*60 + "\n")
    
    # Ensure directories exist
    os.makedirs("models", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # 1. Load historical data
    logger.info("Step 1: Loading 8-year XAUUSD data...")
    df = load_historical_data(CONFIG["hist_data_path"])
    
    # 2. Scan and generate labeled signals
    logger.info("Step 2: Scanning for SMC signals and simulating outcomes...")
    new_records = scan_and_label(
        df,
        sample_every=10,      # Process every 10th candidate
        min_lookback=100,
        tp_rr=2.0,           # 1:2 risk:reward
        sl_pips=50            # 50 pip SL
    )
    logger.info(f"Generated {len(new_records):,} labeled signals")
    
    # 3. Show statistics
    wins = sum(1 for r in new_records if r["outcome"] == 1)
    losses = len(new_records) - wins
    logger.info(f"Win rate: {wins}/{len(new_records)} = {wins/len(new_records)*100:.1f}%")
    
    regimes = {}
    for r in new_records:
        reg = r["signal"].get("regime", "unknown")
        regimes[reg] = regimes.get(reg, 0) + 1
    logger.info(f"Regime distribution: {regimes}")
    
    # 4. Merge with existing trade log
    logger.info("Step 3: Merging with existing trade log...")
    all_records = merge_with_existing(new_records, CONFIG["trade_log_path"])
    
    # 5. Save combined trade log
    logger.info("Step 4: Saving enhanced trade log...")
    save_trade_log(all_records, CONFIG["trade_log_path"])
    
    # 6. Train LightGBM model
    logger.info("Step 5: Training LightGBM model...")
    success = train_lightgbm(all_records)
    
    if success:
        print("\n" + "="*60)
        print("✅ ML MODEL TRAINING COMPLETE")
        print("="*60)
        print(f"  • Model saved: models/lgbm_signal_filter.pkl")
        print(f"  • Training samples: {len(all_records)}")
        print(f"  • Historical win rate: {wins/len(new_records)*100:.1f}%")
        print("="*60 + "\n")
    else:
        print("\n❌ Training failed - insufficient data\n")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())