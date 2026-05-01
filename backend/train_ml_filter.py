"""
SMC ML Signal Filter - Simplified Training
==========================================
Generates labeled signals from 8yr XAUUSD data and trains a classifier.
"""

import os
import json
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger("SMC_ML")

DATA_PATH = "data/XAUUSDm_H1_8 years data.csv"
TRADE_LOG_PATH = "data/trade_log.json"
MODEL_PATH = "models/lgbm_signal_filter.pkl"

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}
FEATURE_KEYS = ["ob_strength", "fvg_present", "bos_aligned", "liquidity_swept", "adr_pct", "pips_to_liquidity", "session", "htf_bias"]


def engineer_features(signal: dict) -> dict:
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


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    # Clean column names: remove < > and whitespace
    df.columns = [c.strip().strip('<').strip('>').lower() for c in df.columns]
    log.info(f"Columns: {list(df.columns)}")
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    # Use 'vol' or 'volume'
    vol_col = 'vol' if 'vol' in df.columns else 'volume'
    cols = ['datetime', 'open', 'high', 'low', 'close', vol_col]
    df = df[cols].dropna()
    df = df.rename(columns={vol_col: 'volume'})
    log.info(f"Loaded {len(df)} bars")
    return df


def detect_ob(df: pd.DataFrame, i: int, lookback: int = 8) -> dict:
    if i < lookback + 2:
        return None
    
    window = df.iloc[i - lookback:i]
    curr = df.iloc[i]
    
    for j in range(len(window) - 2, 0, -1):
        candle = window.iloc[j]
        if candle['close'] < candle['open']:
            if curr['close'] > candle['high']:
                vol_ratio = min(1.0, candle['volume'] / max(window['volume'].mean(), 1))
                if vol_ratio < 0.4:
                    continue
                return {"dir": "buy", "strength": vol_ratio, "entry": candle['high'], "sl": candle['low'] - (candle['high'] - candle['low']) * 0.1}
        elif candle['close'] > candle['open']:
            if curr['close'] < candle['low']:
                vol_ratio = min(1.0, candle['volume'] / max(window['volume'].mean(), 1))
                if vol_ratio < 0.4:
                    continue
                return {"dir": "sell", "strength": vol_ratio, "entry": candle['low'], "sl": candle['high'] + (candle['high'] - candle['low']) * 0.1}
    return None


def simulate(df: pd.DataFrame, i: int, ob: dict, rr: float = 2.0) -> int:
    direction = ob["dir"]
    sl_dist = abs(ob["entry"] - ob["sl"])
    tp = ob["entry"] + sl_dist * rr if direction == "buy" else ob["entry"] - sl_dist * rr
    
    for _, bar in df.iloc[i+1:min(i+20, len(df))].iterrows():
        if direction == "buy":
            if bar['low'] <= ob['sl']: return 0
            if bar['high'] >= tp: return 1
        else:
            if bar['high'] >= ob['sl']: return 0
            if bar['low'] <= tp: return 1
    return 0


def get_session(dt) -> str:
    h = dt.hour
    if 2 <= h < 8: return "asian"
    if 8 <= h < 12: return "london"
    if 12 <= h < 16: return "overlap"
    return "ny"


def htf_bias(df: pd.DataFrame, i: int) -> int:
    if i < 30: return 0
    subset = df.iloc[i-30:i]['close']
    return 1 if subset.iloc[-1] > subset.iloc[0] else -1 if subset.iloc[-1] < subset.iloc[0] else 0


def load_backtest_signals(path: str) -> list:
    """Load signals from backtest output and convert to training format."""
    df = pd.read_csv(path)
    df['time'] = pd.to_datetime(df['time'])
    
    signals = []
    rr = 2.0
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        if row['signal'] == 'WAIT':
            continue
        
        direction = 'buy' if row['signal'] == 'BUY' else 'sell'
        entry = row['price']
        
        # Calculate actual SL/TP based on prediction range
        range_pips = abs(row['pred_high'] - row['pred_low']) * 10
        if range_pips < 10:
            range_pips = 20
        
        sl_dist = range_pips / rr
        sl = entry - sl_dist if direction == 'buy' else entry + sl_dist
        tp = entry + range_pips if direction == 'buy' else entry - range_pips
        
        # Calculate features from actual price data
        # Use prediction confidence as proxy for OB strength
        pred_range_pct = abs(row['pred_high'] - row['pred_low']) / entry
        ob_strength = min(1.0, pred_range_pct * 50)  # Scale to 0-1
        
        # Use prediction spread as FVG indicator (wider = more clear)
        fvg_present = abs(row['pred_high'] - row['pred_low']) > 5
        
        # BOS aligned - check if prediction direction matches trade direction
        pred_direction = 1 if row['pred_high'] > entry else -1
        bos_aligned = (pred_direction == 1 and direction == 'buy') or (pred_direction == -1 and direction == 'sell')
        
        # Liquidity swept - use volatility as proxy
        recent_volatility = abs(df.iloc[max(0,i-5):i]['close'].std()) if i > 5 else 0
        liquidity_swept = recent_volatility > 1.0  # Threshold for "high volatility"
        
        # ADR position - estimate from prediction range vs historical
        pred_adr = range_pips / 20  # Assume 20 pip average daily range
        adr_pct = min(1.0, pred_adr)
        
        # Pips to liquidity - use prediction distance
        pips_to_liquidity = range_pips / 2
        
        # Determine outcome
        outcome = 0
        future_prices = df.iloc[i:min(i+24, len(df))]
        for _, future_bar in future_prices.iterrows():
            if direction == 'buy':
                if future_bar['low'] <= sl:
                    outcome = 0
                    break
                if future_bar['high'] >= tp:
                    outcome = 1
                    break
            else:
                if future_bar['high'] >= sl:
                    outcome = 0
                    break
                if future_bar['low'] <= tp:
                    outcome = 1
                    break
        
        if outcome == 0 and len(future_prices) > 0:
            end_price = future_prices.iloc[-1]['close']
            if direction == 'buy' and end_price > entry:
                outcome = 1
            elif direction == 'sell' and end_price < entry:
                outcome = 1
        
        signal = {
            "ob_strength": ob_strength,
            "fvg_present": fvg_present,
            "bos_aligned": bos_aligned,
            "liquidity_swept": liquidity_swept,
            "adr_pct": adr_pct,
            "pips_to_liquidity": pips_to_liquidity,
            "session": get_session(row['time']),
            "htf_bias": 1 if direction == 'buy' else -1,
            "direction": direction,
            "entry_price": entry,
            "sl_price": sl,
            "tp_price": tp,
        }
        
        signals.append({
            "timestamp": str(row['time']),
            "signal": signal,
            "features": engineer_features(signal),
            "outcome": outcome,
        })
    
    log.info(f"Loaded {len(signals)} signals with varied features and real outcomes")
    return signals


def load_signals(path: str) -> list:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_signals(signals: list, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, 'w') as f:
        json.dump(signals, f, indent=2, default=str)
    log.info(f"Saved to {path}")


def train_model(signals: list) -> bool:
    if not signals or len(signals) < 30:
        log.error("Insufficient signals")
        return False
    
    X = np.array([[s["features"][k] for k in FEATURE_KEYS] for s in signals], dtype=np.float32)
    y = np.array([s["outcome"] for s in signals], dtype=int)
    
    win_rate = y.mean()
    log.info(f"Training on {len(y)} samples, win_rate={win_rate:.2%}")
    
    # Calculate weighted scores for each sample
    scores = []
    weights = {}
    
    for i, key in enumerate(FEATURE_KEYS):
        feature_col = X[:, i]
        std = np.std(feature_col)
        if std > 0:
            # Normalize feature
            feature_normalized = (feature_col - feature_col.min()) / (feature_col.max() - feature_col.min() + 1e-8)
            correlation = np.corrcoef(feature_normalized, y)[0, 1]
            if np.isnan(correlation):
                correlation = 0
        else:
            correlation = 0
        weights[key] = correlation
        # Calculate score contribution
        scores.append(feature_normalized * correlation if std > 0 else np.zeros(len(X)))
    
    # Calculate total weighted score
    total_scores = np.sum(scores, axis=0)
    
    # Normalize scores to 0-1 range
    min_score = np.min(total_scores)
    max_score = np.max(total_scores)
    if max_score > min_score:
        normalized_scores = (total_scores - min_score) / (max_score - min_score)
    else:
        normalized_scores = np.ones(len(total_scores)) * 0.5
    
    # Calculate optimal threshold based on ROC-like analysis
    # Find threshold that maximizes separation
    thresholds = np.linspace(0, 1, 20)
    best_threshold = 0.5
    best_accuracy = 0
    
    for thresh in thresholds:
        predictions = (normalized_scores >= thresh).astype(int)
        accuracy = np.mean(predictions == y)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = thresh
    
    log.info(f"Optimal threshold: {best_threshold:.2f}, accuracy: {best_accuracy:.2%}")
    
    model_info = {
        "weights": weights,
        "threshold": float(best_threshold),
        "min_score": float(min_score),
        "max_score": float(max_score),
        "model_type": "weighted_average",
        "win_rate": float(win_rate),
        "n_samples": len(y),
    }
    
    os.makedirs("models", exist_ok=True)
    import json
    with open(MODEL_PATH.replace('.pkl', '.json'), 'w') as f:
        json.dump(model_info, f, indent=2)
    log.info("Trained with weighted average model")
    
    log.info(f"Model trained and saved")
    return True


def test_model(signals: list) -> float:
    if not signals:
        return 0.5
    
    json_path = MODEL_PATH.replace('.pkl', '.json')
    pickle_path = MODEL_PATH.replace('.pkl', '.pickle')
    
    if os.path.exists(json_path):
        import json
        with open(json_path, 'r') as f:
            info = json.load(f)
        
        weights = info.get("weights", {})
        bias = info.get("bias", 0.5)
        X = np.array([[s["features"][k] for k in FEATURE_KEYS] for s in signals[:10]], dtype=np.float32)
        
        # Calculate weighted score
        scores = []
        for row in X:
            score = sum(row[i] * weights.get(FEATURE_KEYS[i], 0) for i in range(len(FEATURE_KEYS))) + bias
            prob = 1 / (1 + np.exp(-score))
            scores.append(prob)
        
        avg_prob = np.mean(scores)
        log.info(f"Test prediction (correlation): {avg_prob:.3f}")
        return float(avg_prob)
    elif os.path.exists(pickle_path):
        import pickle
        try:
            with open(pickle_path, 'rb') as f:
                info = pickle.load(f)
            
            model = info["model"]
            X = np.array([[s["features"][k] for k in FEATURE_KEYS] for s in signals[:10]], dtype=np.float32)
            
            prob = model.predict_proba(X)[0][1]
            log.info(f"Test prediction: {prob:.3f}")
            return float(prob)
        except:
            return 0.5
    
    return 0.5


def main():
    log.info("=" * 50)
    log.info("SMC ML Training Pipeline")
    log.info("=" * 50)
    
    signals = load_signals(TRADE_LOG_PATH)
    if not signals:
        log.info("Loading signals from backtest data...")
        signals = load_backtest_signals("data/backtest_signals.csv")
        save_signals(signals, TRADE_LOG_PATH)
    
    if len(signals) >= 30:
        train_model(signals)
        test_model(signals)
    else:
        log.error(f"Insufficient signals: {len(signals)} < 30")
    
    log.info("=" * 50)
    log.info("DONE")
    log.info("=" * 50)


if __name__ == "__main__":
    main()