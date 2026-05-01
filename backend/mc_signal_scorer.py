"""
MC SIGNAL SCORER
==============
Score new SMC signals using the trained LightGBM model.
Integrates with your existing trading system.
"""

import numpy as np
import joblib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("MC_Scorer")

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias"
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}


class SignalScorer:
    """Score SMC signals using trained LightGBM model."""
    
    def __init__(self, model_path: str = "models/lgbm_signal_filter.pkl"):
        self.model = None
        self.model_path = model_path
        self.threshold = 0.62  # Default threshold
        self._load_model()
    
    def _load_model(self):
        """Load trained LightGBM model."""
        if Path(self.model_path).exists():
            try:
                data = joblib.load(self.model_path)
                self.model = data["model"]
                logger.info(f"Loaded model: {data.get('trained_at')}")
                logger.info(f"Training samples: {data.get('train_samples')}")
                logger.info(f"Win rate: {data.get('train_win_rate')}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
        else:
            logger.error(f"Model not found: {self.model_path}")
    
    def engineer_features(self, signal: dict) -> dict:
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
    
    def features_to_array(self, features: dict) -> np.ndarray:
        """Convert feature dict to numpy array for prediction."""
        return np.array(
            [[features[k] for k in FEATURE_KEYS]],
            dtype=np.float32
        )
    
    def score(self, signal: dict) -> Tuple[bool, float, dict]:
        """
        Score a single SMC signal.
        
        Returns:
            should_trade (bool): Whether to execute the trade
            confidence (float): P(win) from 0.0 to 1.0
            debug (dict): Full breakdown for logging
        """
        if self.model is None:
            logger.warning("No model loaded - allowing all signals")
            return True, 0.5, {"error": "No model loaded"}
        
        features = self.engineer_features(signal)
        X = self.features_to_array(features)
        
        # Get P(win) probability
        prob = self.model.predict_proba(X)[0][1]
        confidence = float(prob)
        
        # Decision
        should_trade = confidence >= self.threshold
        
        debug = {
            "confidence": round(confidence, 4),
            "threshold": self.threshold,
            "decision": "TRADE" if should_trade else "SKIP",
            "features": features
        }
        
        logger.info(
            f"Signal | confidence={confidence:.3f} "
            f"threshold={self.threshold:.2f} => {debug['decision']}"
        )
        
        return should_trade, confidence, debug
    
    def score_batch(self, signals: list) -> list:
        """Score multiple signals."""
        results = []
        for sig in signals:
            should_trade, confidence, debug = self.score(sig)
            results.append({
                "signal": sig,
                "should_trade": should_trade,
                "confidence": confidence,
                "debug": debug
            })
        return results


def create_sample_signals() -> list:
    """Create sample signals for demonstration."""
    return [
        {
            "ob_strength": 0.85,
            "fvg_present": True,
            "bos_aligned": True,
            "liquidity_swept": True,
            "adr_pct": 0.35,
            "pips_to_liquidity": 10.0,
            "session": "london",
            "htf_bias": 1,
            "direction": "buy",
            "entry_price": 2650.0,
            "sl_price": 2640.0,
            "tp_price": 2670.0
        },
        {
            "ob_strength": 0.45,
            "fvg_present": False,
            "bos_aligned": True,
            "liquidity_swept": False,
            "adr_pct": 0.80,
            "pips_to_liquidity": 35.0,
            "session": "asian",
            "htf_bias": 0,
            "direction": "sell",
            "entry_price": 2650.0,
            "sl_price": 2660.0,
            "tp_price": 2630.0
        },
        {
            "ob_strength": 0.72,
            "fvg_present": True,
            "bos_aligned": True,
            "liquidity_swept": True,
            "adr_pct": 0.50,
            "pips_to_liquidity": 15.0,
            "session": "ny",
            "htf_bias": 1,
            "direction": "buy",
            "entry_price": 2650.0,
            "sl_price": 2640.0,
            "tp_price": 2670.0
        }
    ]


def main():
    print("\n" + "="*60)
    print("MC SIGNAL SCORER - LightGBM ML Filter")
    print("="*60 + "\n")
    
    # Initialize scorer
    scorer = SignalScorer()
    
    # Test with sample signals
    print("Testing sample signals:\n")
    signals = create_sample_signals()
    
    for i, sig in enumerate(signals, 1):
        should_trade, confidence, debug = scorer.score(sig)
        
        print(f"Signal {i}:")
        print(f"  OB Strength: {sig['ob_strength']:.2f}")
        print(f"  FVG: {sig['fvg_present']} | BOS: {sig['bos_aligned']} | Liq: {sig['liquidity_swept']}")
        print(f"  Session: {sig['session']} | HTF Bias: {sig['htf_bias']}")
        print(f"  ADR%: {sig['adr_pct']:.2f} | Pips to Liq: {sig['pips_to_liquidity']}")
        print(f"  => Confidence: {confidence:.1%}")
        print(f"  => Decision:  {debug['decision']}")
        print()
    
    # Summary
    trades = sum(1 for s in signals if scorer.score(s)[0])
    print("="*60)
    print(f"Summary: {trades}/{len(signals)} signals would execute")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()