from typing import Dict, List, Optional
from support.strategies.base_strategy import AbstractStrategy
from support.price_action.candlestick_patterns import get_candlestick_signal, recognize_patterns
from support.risk.risk_calculator import RiskCalculator

class CandlestickStrategy(AbstractStrategy):
    def __init__(self):
        self.risk_calc = RiskCalculator()
    
    def evaluate(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        # Use LTF (M5) for precise pattern entries
        candles = ltf_buffer
        if not candles:
            return None

        signal = get_candlestick_signal(candles)
        patterns = recognize_patterns(candles)
        
        if not signal:
            return None

        # Get current price
        current_price = ltf_buffer[-1]["close"]
        
        # Get zone from kwargs if available
        zone = kwargs.get("active_zone")
        
        action = "LONG" if signal == "BUY" else "SHORT"
        risk_params = self.risk_calc.calculate_trade_params(action, current_price, zone)
        
        return {
            "action": action,
            "symbol": "XAUUSD",
            "price": current_price,
            "sl": risk_params["sl"],
            "lots": risk_params["lots"],
            "desc": f"TRIGGER: Candlestick Pattern ({', '.join(patterns)}) | SL: {risk_params['sl_pips']}p",
            "confidence": 0.8
        }
