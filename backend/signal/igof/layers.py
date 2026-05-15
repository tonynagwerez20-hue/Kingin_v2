"""SMC Layers."""
from typing import Dict, Any, List

class FVGLayer:
    def __init__(self, threshold: float = 0.5):
        self._threshold = threshold
    
    def evaluate(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < 3:
            return {"action": "FLAT", "confidence": 0.0}
        for i in range(len(candles) - 2, len(candles) - 4, -1):
            c1, c2, c3 = candles[i], candles[i+1], candles[i+2]
            if c2["low"] > c1["high"]:
                return {"action": "BUY", "confidence": self._threshold, "reason": "FVG_BULLISH"}
            if c2["high"] < c1["low"]:
                return {"action": "SELL", "confidence": self._threshold, "reason": "FVG_BEARISH"}
        return {"action": "FLAT", "confidence": 0.0}


class LiquidityLayer:
    def __init__(self, lookback: int = 20):
        self._lookback = lookback
    
    def evaluate(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < self._lookback:
            return {"action": "FLAT", "confidence": 0.0}
        highs = [c["high"] for c in candles[-self._lookback:]]
        lows = [c["low"] for c in candles[-self._lookback:]]
        current = candles[-1]
        if current["high"] > max(highs[:-1]):
            return {"action": "SELL", "confidence": 0.6, "reason": "LIQUIDITY_HIGH"}
        if current["low"] < min(lows[:-1]):
            return {"action": "BUY", "confidence": 0.6, "reason": "LIQUIDITY_LOW"}
        return {"action": "FLAT", "confidence": 0.0}


class MSSLayer:
    def __init__(self, lookback: int = 5):
        self._lookback = lookback
    
    def evaluate(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < self._lookback + 1:
            return {"action": "FLAT", "confidence": 0.0}
        recent = candles[-self._lookback:]
        trend_up = sum(1 for c in range(len(recent)-1) if recent[c+1]["close"] > recent[c]["close"])
        if trend_up > self._lookback * 0.7:
            return {"action": "BUY", "confidence": 0.5, "reason": "MSS_UP"}
        elif trend_up < self._lookback * 0.3:
            return {"action": "SELL", "confidence": 0.5, "reason": "MSS_DOWN"}
        return {"action": "FLAT", "confidence": 0.0}


class DisplacementLayer:
    def __init__(self, min_displacement: float = 0.5):
        self._min = min_displacement
    
    def evaluate(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(candles) < 5:
            return {"action": "FLAT", "confidence": 0.0}
        recent = candles[-5:]
        if recent[-1]["close"] > (recent[-2]["high"] + recent[-2]["low"]) / 2 and recent[-1]["close"] > recent[-2]["close"]:
            return {"action": "BUY", "confidence": 0.4, "reason": "DISPLACEMENT_UP"}
        if recent[-1]["close"] < (recent[-2]["high"] + recent[-2]["low"]) / 2 and recent[-1]["close"] < recent[-2]["close"]:
            return {"action": "SELL", "confidence": 0.4, "reason": "DISPLACEMENT_DOWN"}
        return {"action": "FLAT", "confidence": 0.0}