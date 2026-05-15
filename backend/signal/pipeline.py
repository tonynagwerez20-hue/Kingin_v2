"""Signal Pipeline — Pure function."""
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class SignalDecision:
    action: str
    confidence: float = 0.0
    reason: str = ""
    layers_triggered: List[str] = None


class SignalPipeline:
    def __init__(self):
        self._layers = []
    
    def add_layer(self, layer):
        self._layers.append(layer)
    
    def evaluate(self, candles: List[Dict[str, Any]]) -> SignalDecision:
        if not candles or len(candles) < 10:
            return SignalDecision(action="FLAT", reason="INSUFFICIENT_DATA")
        
        buy_score = sell_score = 0.0
        triggered = []
        
        for layer in self._layers:
            try:
                result = layer.evaluate(candles)
                if result.get("action") == "BUY":
                    buy_score += result.get("confidence", 0.5)
                    triggered.append(layer.__class__.__name__)
                elif result.get("action") == "SELL":
                    sell_score += result.get("confidence", 0.5)
                    triggered.append(layer.__class__.__name__)
            except:
                pass
        
        if buy_score > sell_score and buy_score > 0.5:
            return SignalDecision(action="BUY", confidence=buy_score, reason=f"BUY from {len(triggered)} layers", layers_triggered=triggered)
        elif sell_score > buy_score and sell_score > 0.5:
            return SignalDecision(action="SELL", confidence=sell_score, reason=f"SELL from {len(triggered)} layers", layers_triggered=triggered)
        
        return SignalDecision(action="FLAT", reason="NO_CLEAR_SIGNAL")


_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = SignalPipeline()
    return _pipeline