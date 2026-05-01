from typing import Dict, List, Any, Optional
import pandas as pd
from support.strategies.base_strategy import AbstractStrategy
from support.price_action.supply_and_demand import detect_supply_demand, mitigate_zones

class FilterTwo(AbstractStrategy):
    """
    Legacy Filter Two: MTF Zone Analysis (M15).
    Verifies if price is currently inside an active Supply or Demand zone.
    """
    def evaluate(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        if not mtf_buffer:
            return None
            
        df_m15 = pd.DataFrame(mtf_buffer)
        current_price = mtf_buffer[-1]["close"]
        
        zones = detect_supply_demand(df_m15)
        active_zones = mitigate_zones(zones, current_price)
        
        for z in active_zones:
            if z["type"] == "demand" and z["low"] <= current_price <= z["high"]:
                return {
                    "action": "LONG", 
                    "desc": "FilterTwo: Price in Demand Zone", 
                    "confidence": 1.0,
                    "active_zone": z  # Pass zone to OrderflowStrategy
                }
            if z["type"] == "supply" and z["low"] <= current_price <= z["high"]:
                return {
                    "action": "SHORT", 
                    "desc": "FilterTwo: Price in Supply Zone", 
                    "confidence": 1.0,
                    "active_zone": z  # Pass zone to OrderflowStrategy
                }
                
        return None
