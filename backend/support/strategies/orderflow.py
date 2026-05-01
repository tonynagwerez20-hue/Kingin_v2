from typing import Dict, List, Any, Optional
from support.strategies.base_strategy import AbstractStrategy
from support.orderflow.delta_logic import evaluate_delta, get_delta_direction
from support.risk.risk_calculator import RiskCalculator

class OrderflowStrategy(AbstractStrategy):
    def __init__(self):
        self.risk_calc = RiskCalculator()
    
    def evaluate(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        delta_struct = kwargs.get("delta_struct")
        if not delta_struct:
            return None

        delta_signal = evaluate_delta(delta_struct)
        if not delta_signal or delta_signal == "WAIT":
            return None

        direction = get_delta_direction(delta_signal)
        

        # 2. Entry Trigger Strategy (SURGE, FLIP, or TRANSITION)
        if "SURGE" in delta_signal or "FLIP" in delta_signal or "TRANSITION" in delta_signal:
            # Get current price from MTF buffer
            current_price = mtf_buffer[-1]["close"] if mtf_buffer else ltf_buffer[-1]["close"]
            
            # Get zone from kwargs if available (passed from FilterTwo)
            zone = kwargs.get("active_zone")
            
            # Calculate risk parameters (SL and Lots only - no TP)
            action = "LONG" if direction == "BUY" else "SHORT"
            risk_params = self.risk_calc.calculate_trade_params(action, current_price, zone)
            
            return {
                "action": action,
                "symbol": "XAUUSD",
                "price": current_price,
                "sl": risk_params["sl"],
                "lots": risk_params["lots"],
                "desc": f"TRIGGER: Delta Logic {delta_signal} | SL: {risk_params['sl_pips']}p",
                "confidence": 0.9 if "SURGE" in delta_signal else 0.7
            }
        
        return None
