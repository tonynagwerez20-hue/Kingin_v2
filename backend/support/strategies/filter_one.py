from typing import Dict, List, Any, Optional
from support.strategies.base_strategy import AbstractStrategy
from support.price_action.bias import calculate_structure_bias

class FilterOne(AbstractStrategy):
    """
    Legacy Filter One: HTF Bias Analysis (H1).
    Determines if the structural trend is BULLISH or BEARISH.
    """
    def evaluate(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        bias = calculate_structure_bias(htf_buffer)
        
        if bias == "BULLISH":
            return {"action": "LONG", "desc": "FilterOne: Bullish Structure confirmed", "confidence": 1.0}
        elif bias == "BEARISH":
            return {"action": "SHORT", "desc": "FilterOne: Bearish Structure confirmed", "confidence": 1.0}
            
        return None
