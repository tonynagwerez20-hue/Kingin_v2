from typing import Dict, Optional
from pathlib import Path

class RiskCalculator:
    """
    Shared risk calculation logic for all strategies.
    Calculates Stop Loss and Lot Size based on zone boundaries.
    No Take Profit - exits managed by orderflow reversals.
    """
    
    def __init__(self, 
                 account_balance: float = 10000.0,
                 pip_value: float = 10.0,
                 pip_size: float = 0.01,
                 risk_percent: float = 0.001,  # 0.1% risk per trade
                 zone_padding_pips: float = 2.0):
        self.account_balance = account_balance
        self.pip_value = pip_value
        self.pip_size = pip_size
        self.risk_percent = risk_percent
        self.zone_padding_pips = zone_padding_pips
    
    def calculate_trade_params(self, 
                               direction: str, 
                               current_price: float,
                               zone: Optional[Dict] = None) -> Dict:
        """
        Calculate SL and Lots for a trade with safety limits and validation.
        """
        # 1. Input Validation
        if direction not in ["LONG", "SHORT"]:
            raise ValueError(f"Invalid direction: {direction}")
        if current_price <= 0:
            raise ValueError(f"Invalid price: {current_price}")
            
        if not zone:
            # Fallback: use fixed pip distance if no zone provided
            sl_distance_pips = 20.0
            if direction == "LONG":
                sl = current_price - (sl_distance_pips * self.pip_size)
            else:
                sl = current_price + (sl_distance_pips * self.pip_size)
        else:
            # Use zone boundaries for SL placement
            if direction == "LONG":
                sl = zone["low"] - (self.zone_padding_pips * self.pip_size)
                sl_distance_pips = (current_price - sl) / self.pip_size
            else:
                sl = zone["high"] + (self.zone_padding_pips * self.pip_size)
                sl_distance_pips = (sl - current_price) / self.pip_size
        
        # 2. Safety Checks (Minimum/Maximum SL)
        MIN_SL_PIPS = 5.0
        MAX_SL_PIPS = 30.0  # Institutional Safety Cap for Gold
        
        if sl_distance_pips < MIN_SL_PIPS:
            sl_distance_pips = MIN_SL_PIPS
            # Recalculate SL Price based on capped pips
            if direction == "LONG":
                sl = current_price - (sl_distance_pips * self.pip_size)
            else:
                sl = current_price + (sl_distance_pips * self.pip_size)
        
        if sl_distance_pips > MAX_SL_PIPS:
            sl_distance_pips = MAX_SL_PIPS
            # Recalculate SL Price based on capped pips
            if direction == "LONG":
                sl = current_price - (sl_distance_pips * self.pip_size)
            else:
                sl = current_price + (sl_distance_pips * self.pip_size)
        
        # 3. Lot Calculation (Strict Equity/Risk formula)
        risk_amount = self.account_balance * self.risk_percent
        # Prevention against division by zero if pip_value or sl_distance is 0
        divisor = (sl_distance_pips * self.pip_value)
        if divisor <= 0:
            lots = 0.01 # Safe minimum
        else:
            lots = risk_amount / divisor
        
        # Enforce broker lot limits
        lots = max(0.01, min(lots, 10.0))
        lots = round(lots, 2)
        
        return {
            "sl": round(sl, 2),
            "lots": lots,
            "sl_pips": round(sl_distance_pips, 1),
            "is_capped": sl_distance_pips == MAX_SL_PIPS
        }
