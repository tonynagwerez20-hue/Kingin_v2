"""
MC ML INTEGRATION ADAPTER
======================
Adapter to integrate LightGBM signal filtering with your existing trading system.
Drop-in replacement for signal filtering layer.

Usage:
    from mc_ml_integration import MLSignalFilter
    
    ml_filter = MLSignalFilter()
    
    # In your signal generation flow:
    should_trade, confidence, debug = ml_filter.evaluate(signal_dict)
    
    if should_trade:
        # Execute trade
        pass
    else:
        # Skip signal
        pass
"""

import numpy as np
import joblib
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("ML_Filter")

FEATURE_KEYS = [
    "ob_strength", "fvg_present", "bos_aligned", "liquidity_swept",
    "adr_pct", "pips_to_liquidity", "session", "htf_bias"
]

SESSION_MAP = {"asian": 0, "london": 1, "overlap": 2, "ny": 3}


class MLSignalFilter:
    """
    LightGBM-powered signal filter.
    Scores SMC signals and decides whether to execute or skip.
    """
    
    DEFAULT_THRESHOLD = 0.62
    
    def __init__(
        self,
        model_path: str = "models/lgbm_signal_filter.pkl",
        threshold: float = None
    ):
        self.model = None
        self.model_path = model_path
        self.threshold = threshold or self.DEFAULT_THRESHOLD
        self._load_model()
    
    def _load_model(self):
        """Load trained LightGBM model."""
        if Path(self.model_path).exists():
            try:
                data = joblib.load(self.model_path)
                self.model = data["model"]
                self.trained_at = data.get("trained_at")
                self.train_samples = data.get("train_samples")
                self.train_win_rate = data.get("train_win_rate")
                
                logger.info(f"ML Filter loaded:")
                logger.info(f"  Model: {self.model_path}")
                logger.info(f"  Trained: {self.trained_at}")
                logger.info(f"  Samples: {self.train_samples}")
                logger.info(f"  Win rate: {self.train_win_rate:.1%}")
                logger.info(f"  Threshold: {self.threshold}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                logger.warning("Running in pass-through mode (all signals allowed)")
        else:
            logger.warning(f"Model not found: {self.model_path}")
            logger.warning("Running in pass-through mode (all signals allowed)")
    
    def engineer_features(self, signal: dict) -> dict:
        """
        Convert SMC signal dict to ML feature vector.
        
        Expected signal dict fields:
            ob_strength: float (0.0-1.0)
            fvg_present: bool
            bos_aligned: bool  
            liquidity_swept: bool
            adr_pct: float (0.0-1.0)
            pips_to_liquidity: float
            session: str ("asian"|"london"|"overlap"|"ny")
            htf_bias: int (-1|0|1)
        """
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
    
    def _to_array(self, features: dict) -> np.ndarray:
        """Convert feature dict to numpy array."""
        return np.array(
            [[features[k] for k in FEATURE_KEYS]],
            dtype=np.float32
        )
    
    def evaluate(self, signal: dict) -> Tuple[bool, float, dict]:
        """
        Evaluate a trading signal through the ML filter.
        
        Args:
            signal: dict containing SMC signal data
            
        Returns:
            should_trade: bool - whether to execute the trade
            confidence: float - P(win) from 0.0 to 1.0
            debug: dict - detailed breakdown
        """
        # Pass-through mode if no model
        if self.model is None:
            return True, 0.5, {"mode": "pass-through", "reason": "no_model"}
        
        # Engineer features
        features = self.engineer_features(signal)
        X = self._to_array(features)
        
        # Get prediction
        prob = self.model.predict_proba(X)[0][1]
        confidence = float(prob)
        
        # Decision
        should_trade = confidence >= self.threshold
        
        debug = {
            "confidence": round(confidence, 4),
            "threshold": self.threshold,
            "decision": "TRADE" if should_trade else "SKIP",
            "ob_strength": features["ob_strength"],
            "fvg_present": bool(features["fvg_present"]),
            "bos_aligned": bool(features["bos_aligned"]),
            "liquidity_swept": bool(features["liquidity_swept"]),
            "adr_pct": features["adr_pct"],
            "pips_to_liquidity": features["pips_to_liquidity"],
            "session": features["session"],
            "htf_bias": features["htf_bias"]
        }
        
        # Log decision
        if should_trade:
            logger.info(
                f"ML Filter: CONF={confidence:.2%} > THRESH={self.threshold:.2%} => TRADE "
                f"(OB={features['ob_strength']:.2f} Liq={features['pips_to_liquidity']:.0f}pips)"
            )
        else:
            logger.info(
                f"ML Filter: CONF={confidence:.2%} < THRESH={self.threshold:.2%} => SKIP "
                f"(OB={features['ob_strength']:.2f} Liq={features['pips_to_liquidity']:.0f}pips)"
            )
        
        return should_trade, confidence, debug
    
    def set_threshold(self, threshold: float):
        """Adjust the confidence threshold."""
        old = self.threshold
        self.threshold = threshold
        logger.info(f"Threshold adjusted: {old:.2%} => {threshold:.2%}")
    
    def get_status(self) -> dict:
        """Get ML filter status."""
        return {
            "model_loaded": self.model is not None,
            "threshold": self.threshold,
            "trained_at": str(self.trained_at) if self.trained_at else None,
            "train_samples": self.train_samples,
            "train_win_rate": self.train_win_rate
        }


def create_from_strategy_signal(strategy_signal: dict) -> dict:
    """
    Convert SMCStrategy signal output to ML filter format.
    
    Your SMCStrategy outputs:
        {
            "action": "TRADE",
            "direction": "BUY",
            "price": 2650.0,
            "sl": 2640.0,
            "tp": 2670.0,
            "confidence": 0.75,
            "reason": "...",
            "layer_details": {...}
        }
    
    Convert to ML filter format:
        {
            "ob_strength": 0.75,        # from layer confidence
            "fvg_present": True,        # from layer_details
            "bos_aligned": True,        # from MechanicalStructure
            "liquidity_swept": True,   # from LiquiditySweep
            "adr_pct": 0.5,            # calculate from current price
            "pips_to_liquidity": 15.0, # extract from signal data
            "session": "london",        # determine from time
            "htf_bias": 1             # from H4/H1 direction
        }
    """
    details = strategy_signal.get("layer_details", {})
    
    # Extract layer statuses
    fvg_layer = details.get("FVGDiscount", {})
    liq_layer = details.get("LiquiditySweep", {})
    bos_layer = details.get("MechanicalStructure", {})
    
    # Map to feature format
    ml_signal = {
        "ob_strength": strategy_signal.get("confidence", 0.5),
        "fvg_present": bool(fvg_layer.get("status", False)),
        "bos_aligned": bool(bos_layer.get("status", False)),
        "liquidity_swept": bool(liq_layer.get("status", False)),
        # These need to be calculated/passed from your system
        "adr_pct": 0.5,
        "pips_to_liquidity": 20.0,
        "session": "london",
        "htf_bias": 1 if strategy_signal.get("direction") == "BUY" else -1
    }
    
    return ml_signal


# Integration example for your generate_backtest_signals.py flow:
"""
# In generate_backtest_signals.py, after getting signal from SMCStrategy:

from mc_ml_integration import MLSignalFilter

# Initialize once at startup
ml_filter = MLSignalFilter()

# In signal processing loop:
signal = strategy.generate_signal(snapshot)

if signal.get("action") == "TRADE":
    # Convert to ML format
    ml_signal = create_from_strategy_signal(signal)
    
    # Evaluate through ML filter
    should_trade, confidence, debug = ml_filter.evaluate(ml_signal)
    
    if should_trade:
        # Execute with normal risk management
        risk_result = risk_rule.check_risk(signal)
        if risk_result.get("allowed"):
            execution_signals.append(...)
    else:
        # ML filtered - log as skipped
        logger.debug(f"ML filtered: {debug}")
"""