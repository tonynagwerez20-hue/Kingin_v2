"""
RegimeLayer - Gold Calibrated Edition
Volatility-based execution throttling.
"""

import numpy as np
from typing import List, Dict

class RegimeLayer:
    """
    Analyzes market volatility and structure to determine the current trading regime.
    Used by the Risk Manager to veto trades during high-risk conditions.
    """
    def __init__(self):
        self.current_regime = "STABLE"
        self.history = []
        self.window = 20

    def detect_regime(self, m15_candles: List[Dict]) -> str:
        """
        Detects the current market regime based on M15 volatility.
        
        Regimes:
        - STABLE: Normal conditions, execution allowed.
        - VOLATILE: High ATR/Standard Deviation, execution restricted.
        - RANGING: Low volatility/choppy, execution restricted.
        """
        if len(m15_candles) < self.window:
            return "STABLE"

        # Extract closes and calculate returns
        closes = np.array([c['close'] for c in m15_candles[-self.window:]])
        returns = np.diff(closes)
        
        # Calculate volatility metrics
        volatility = np.std(returns)
        
        # Calculate range metrics (ATR-like)
        highs = np.array([c['high'] for c in m15_candles[-self.window:]])
        lows = np.array([c['low'] for c in m15_candles[-self.window:]])
        avg_range = np.mean(highs - lows)

        # Thresholds (XAUUSD Calibrated)
        # These values represent pip-equivalent moves on M15
        if volatility > 2.5 or avg_range > 5.0:
            regime = "VOLATILE"
        elif volatility < 0.4 and avg_range < 0.8:
            regime = "RANGING"
        else:
            regime = "STABLE"

        self.current_regime = regime
        return regime

    def get_status(self) -> Dict:
        return {
            "current_regime": self.current_regime,
            "layer_name": "VolatilityRegime"
        }
