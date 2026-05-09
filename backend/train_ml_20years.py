import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import lightgbm as lgb
import joblib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ML20YearPipeline")

def check_data():
    path = Path("data/backtest_20y/real_signals_20y.json")
    if not path.exists():
        logger.error(f"✗ Real signals file missing: {path}")
        return False
    
    with open(path) as f:
        signals = json.load(f)
    logger.info(f"✓ Found {len(signals)} REAL training signals from 20-year history.")
    return signals

def train_lgbm(signals: List[Dict]):
    logger.info("SECTION: Training LightGBM on 20-Year Institutional Data")
    
    FEATURE_KEYS = [
        "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
        "adr_pct", "pips_to_liquidity", "session", "htf_bias"
    ]
    
    X = []
    y = []
    
    for s in signals:
        feat = s.get("features", {})
        X.append([feat.get(k, 0) for k in FEATURE_KEYS])
        y.append(s.get("outcome", 0))
        
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=int)
    
    # Model parameters for institutional precision
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "n_estimators": 500,
        "learning_rate": 0.03,
        "max_depth": 7,
        "num_leaves": 63,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "verbose": -1,
        "random_state": 42
    }
    
    model = lgb.LGBMClassifier(**params)
    model.fit(X, y)
    
    accuracy = np.mean(model.predict(X) == y)
    logger.info(f"✓ Training Complete. Samples: {len(y)}, Accuracy: {accuracy:.2%}")
    
    # Feature Importance
    importances = dict(zip(FEATURE_KEYS, model.feature_importances_))
    logger.info(f"Top Features: {sorted(importances.items(), key=lambda x: -x[1])[:3]}")
    
    # Save as JSON-compatible format for the Hybrid Engine
    model_data = {
        "weights": {k: float(v) for k, v in zip(FEATURE_KEYS, model.feature_importances_)},
        "threshold": 0.65,
        "model_type": "lightgbm_static_20y",
        "training_accuracy": float(accuracy),
        "n_samples": len(y),
        "feature_keys": FEATURE_KEYS,
        "trained_at": datetime.now().isoformat()
    }
    
    os.makedirs("models", exist_ok=True)
    out_path = "models/lgbm_signal_filter_20y.json"
    with open(out_path, 'w') as f:
        json.dump(model_data, f, indent=2)
    
    logger.info(f"✓ Model saved to {out_path}")
    return True

def main():
    signals = check_data()
    if not signals: return 1
    
    if train_lgbm(signals):
        print("\n" + "="*60)
        print("✅ 20-YEAR INSTITUTIONAL ML TRAINING COMPLETE")
        print("="*60 + "\n")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
