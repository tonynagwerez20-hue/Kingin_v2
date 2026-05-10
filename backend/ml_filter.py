"""
ML Signal Filter Integration Module
====================================
Provides ML-based signal filtering for the SMC trading system.
Uses correlation-based model trained on historical backtest data.
"""

import os
import json
import logging
import numpy as np
from datetime import datetime

log = logging.getLogger("ML_Filter")

MODEL_PATH = "models/lgbm_signal_filter_20y.json"
TRADE_LOG_PATH = "data/trade_log.json"
# Threshold will be loaded from model or use default
CONFIG = {
    "threshold": 0.65,  # Higher precision for 20y model
}

def get_threshold() -> float:
    """Get threshold from model config."""
    model_info = load_model()
    if model_info and "threshold" in model_info:
        return model_info["threshold"]
    return CONFIG["threshold"]

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias",
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}


def engineer_features(signal: dict) -> dict:
    """Convert signal dict to ML feature vector."""
    return {
        "ob_strength": float(signal.get("ob_strength", 0.50)),
        "fvg_present": int(bool(signal.get("fvg_present", False))),
        "bos_aligned": int(bool(signal.get("bos_aligned", False))),
        "liquidity_swept": int(bool(signal.get("liquidity_swept", False))),
        "adr_pct": float(signal.get("adr_pct", 0.50)),
        "pips_to_liquidity": float(signal.get("pips_to_liquidity", 20.0)),
        "session": float(SESSION_MAP.get(signal.get("session", "london"), 1)),
        "htf_bias": float(signal.get("htf_bias", 0)),
    }


def load_model() -> dict:
    """Load trained model from JSON file with safety guards."""
    if not os.path.exists(MODEL_PATH):
        # Create a dummy default model structure if missing to prevent pipeline crashes
        log.warning(f"ML Model file NOT FOUND at {MODEL_PATH}. Using default conservative weights.")
        return {
            "model_type": "default_conservative",
            "threshold": 0.65,
            "weights": {
                "ob_strength": 0.2,
                "fvg_present": 0.2,
                "bos_aligned": 0.2,
                "liquidity_swept": 0.3,
                "adr_pct": -0.1,
                "pips_to_liquidity": 0.1,
                "session": 0.05,
                "htf_bias": 0.05
            }
        }
    
    try:
        with open(MODEL_PATH) as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to parse ML model file: {e}")
        return None


def score_signal(features: dict) -> float:
    """
    Score a signal using the trained model.
    Returns confidence 0.0-1.0.
    """
    model_info = load_model()
    
    if model_info is None:
        log.warning("No trained model found - returning default confidence 0.5")
        return 0.5
    
    weights = model_info.get("weights", {})
    
    # Convert features to numeric array
    feature_vector = []
    for key in FEATURE_KEYS:
        val = features.get(key, 0)
        
        if isinstance(val, str):
            val = SESSION_MAP.get(val, 1)
        elif isinstance(val, bool):
            val = 1 if val else 0
        else:
            val = float(val)
        
        feature_vector.append(float(val))
    
    # Normalize features to training range before calculating score
    # This ensures new signals are scored in the same space as training
    feature_ranges = {
        'ob_strength': (0.0, 1.0),
        'fvg_present': (0.0, 1.0),
        'bos_aligned': (0.0, 1.0),
        'liquidity_swept': (0.0, 1.0),
        'adr_pct': (0.0, 1.0),
        'pips_to_liquidity': (0.0, 100.0),  # Cap at reasonable range
        'session': (0.0, 3.0),
        'htf_bias': (-1.0, 1.0),
    }
    
    normalized_vector = []
    for i, key in enumerate(FEATURE_KEYS):
        val = feature_vector[i]
        min_v, max_v = feature_ranges.get(key, (0, 1))
        if max_v > min_v:
            norm_val = (val - min_v) / (max_v - min_v)
            norm_val = max(0, min(1, norm_val))  # Clip to 0-1
        else:
            norm_val = 0.5
        normalized_vector.append(norm_val)
    
    # Calculate weighted score
    score = sum(normalized_vector[i] * weights.get(FEATURE_KEYS[i], 0) for i in range(len(FEATURE_KEYS)))
    
    # Use dynamic score range based on feature weights
    max_score = sum(abs(v) for v in weights.values())
    if max_score > 0:
        confidence = score / max_score
    else:
        confidence = 0.5
    
    return float(np.clip(confidence, 0.0, 1.0))


def should_trade(features: dict) -> tuple[bool, float, dict]:
    """
    Determine if signal should be traded.
    
    Returns:
        (should_trade: bool, confidence: float, debug: dict)
    """
    confidence = score_signal(features)
    threshold = get_threshold()
    should_trade = confidence >= threshold
    
    debug = {
        "confidence": round(confidence, 4),
        "threshold": threshold,
        "decision": "TRADE" if should_trade else "SKIP",
    }
    
    log.info(f"ML Filter: conf={confidence:.3f} thresh={threshold:.2f} → {debug['decision']}")
    
    return should_trade, confidence, debug


def log_outcome(signal: dict, features: dict, confidence: float, outcome: int):
    """Log trade outcome for future retraining."""
    log_entry = {
        "timestamp": str(datetime.now()),
        "signal": signal,
        "features": features,
        "confidence": confidence,
        "outcome": outcome,
    }
    
    if os.path.exists(TRADE_LOG_PATH):
        with open(TRADE_LOG_PATH) as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(TRADE_LOG_PATH, 'w') as f:
        json.dump(logs, f, indent=2, default=str)


def get_model_status() -> dict:
    """Get current model status."""
    model_info = load_model()
    if model_info:
        return {
            "loaded": True,
            "model_type": model_info.get("model_type", "unknown"),
            "n_samples": model_info.get("n_samples", 0),
            "win_rate": model_info.get("win_rate", 0),
        }
    return {"loaded": False}


# For direct testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("ML Signal Filter Analysis")
    print("=" * 60)
    
    # Load and display model info
    model_info = load_model()
    if model_info:
        print(f"\nModel Status:")
        print(f"  Type: {model_info.get('model_type', 'unknown')}")
        print(f"  Samples: {model_info.get('n_samples', 0)}")
        print(f"  Win Rate: {model_info.get('win_rate', 0):.2%}")
        
        print(f"\nFeature Weights:")
        weights = model_info.get('weights', {})
        for k, v in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
            direction = "+" if v > 0 else "-"
            print(f"  {k:20s}: {v:+.4f} ({direction})")
    
    # Test with different signal types
    test_cases = [
        {
            "name": "Strong Bullish Signal (FVG + Liquidity Swept)",
            "features": {
                "ob_strength": 0.84,
                "fvg_present": True,
                "bos_aligned": True,
                "liquidity_swept": True,
                "adr_pct": 0.3,
                "pips_to_liquidity": 10.0,
                "session": "london",
                "htf_bias": 1,
            }
        },
        {
            "name": "Weak Signal (No FVG, No Liquidity)",
            "features": {
                "ob_strength": 0.5,
                "fvg_present": False,
                "bos_aligned": True,
                "liquidity_swept": False,
                "adr_pct": 0.6,
                "pips_to_liquidity": 30.0,
                "session": "ny",
                "htf_bias": 0,
            }
        },
        {
            "name": "High ADR Signal (Near top of range)",
            "features": {
                "ob_strength": 0.7,
                "fvg_present": True,
                "bos_aligned": True,
                "liquidity_swept": False,
                "adr_pct": 0.85,
                "pips_to_liquidity": 20.0,
                "session": "london",
                "htf_bias": 1,
            }
        },
    ]
    
    print("\n" + "=" * 60)
    print("Signal Scoring Tests")
    print("=" * 60)
    
    for tc in test_cases:
        print(f"\n{tc['name']}:")
        trade, confidence, debug = should_trade(tc['features'])
        print(f"  Confidence: {confidence:.4f}")
        print(f"  Threshold:  {debug['threshold']}")
        print(f"  Decision:   {debug['decision']}")
    
    print("\n" + "=" * 60)