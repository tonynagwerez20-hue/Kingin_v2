from typing import Dict, List, Any, Optional
import pandas as pd
import time

from support.strategies.base_strategy import AbstractStrategy
from support.price_action.bias import calculate_structure_bias
from support.price_action.supply_and_demand import detect_supply_demand, mitigate_zones
from support.orderflow.delta_logic import evaluate_delta, detect_delta_reversal, get_delta_direction
from risk.risk_config import calculate_lot_size

class CompositeStrategy(AbstractStrategy):
    def __init__(self, 
                 account_balance: float = 10000.0,
                 pip_value: float = 10.0,
                 pip_size: float = 0.01,
                 zone_padding: float = 2.0,
                 exit_on_weak_reversal: bool = True,
                 allow_reversals: bool = True,
                 min_time_between_signals: int = 10):
        
        self.account_balance = account_balance
        self.pip_value = pip_value
        self.pip_size = pip_size
        self.zone_padding = zone_padding
        self.exit_on_weak_reversal = exit_on_weak_reversal
        self.allow_reversals = allow_reversals
        self.min_time_between_signals = min_time_between_signals
        
        # State
        self.previous_delta_signal = None
        self.last_signal_time = 0
        self.active_zones = []

    def evaluate(self, 
                 htf_buffer: List[Dict], 
                 mtf_buffer: List[Dict], 
                 ltf_buffer: List[Dict], 
                 **kwargs) -> Optional[Dict]:
        
        delta_struct = kwargs.get("delta_struct")
        position_tracker = kwargs.get("position_tracker")
        
        if not delta_struct or not mtf_buffer or not htf_buffer:
            return None
            
        current_time = time.time()
        
        # --- 1. Data Preparation ---
        current_price = mtf_buffer[-1]["close"]
        delta_signal = evaluate_delta(delta_struct)
        
        # --- 2. Filter 1: Bias (H1) ---
        # Note: calculate_structure_bias currently reads from global buffers. 
        # Ideally we refactor it to accept buffer input, but for now we rely on the shared state.
        bias = calculate_structure_bias("H1")
        
        # --- 3. Filter 2: Zones (M15) + Mitigation ---
        # Re-detect zones occasionally or on every tick? 
        # Optimally: Detect on new candle, Mitigate on every tick.
        # For simplicity in this batch flow: Detect fresh from batch.
        df_m15 = pd.DataFrame(list(mtf_buffer))
        detected_zones = detect_supply_demand(df_m15) or []
        
        # Mitigate
        self.active_zones = mitigate_zones(detected_zones, current_price)
        
        # Check if in zone
        in_demand = False
        in_supply = False
        current_active_zone = None
        
        for z in self.active_zones:
            if z["type"] == "demand" and z["low"] <= current_price <= z["high"]:
                in_demand = True
                current_active_zone = z
            if z["type"] == "supply" and z["low"] <= current_price <= z["high"]:
                in_supply = True
                current_active_zone = z

        # --- CVD Check ---
        cumulative_delta = delta_struct.get("cumulative", [])
        curr_cumulative_delta = cumulative_delta[0] if cumulative_delta else 0
        cvd_bullish = curr_cumulative_delta > 0
        cvd_bearish = curr_cumulative_delta < 0

        # --- 4. Logic & Signal Generation ---
        
        print(f"DEBUG: Bias={bias}, Delta={delta_signal}, InDemand={in_demand}, InSupply={in_supply}, CVD_Bull={cvd_bullish}")
        
        signal_object = None
        
        # A. Exit / Reversal Logic
        if position_tracker and position_tracker.has_position() and delta_signal:
             # Check Reversal
             strong_only = not self.exit_on_weak_reversal
             if detect_delta_reversal(self.previous_delta_signal, delta_signal, strong_only):
                # ... [Reversal Logic Similar to Main Loop] ...
                # For brevity and modularity, let's focus on the generated Signal Object.
                # If we want to handle full execution logic here:
                
                delta_dir = get_delta_direction(delta_signal)
                current_pos_dir = position_tracker.get_position_direction() # e.g. "LONG"
                
                reversal_type = None
                if self.allow_reversals:
                     if delta_dir == "BUY" and in_demand and bias == "BULLISH" and cvd_bullish:
                         reversal_type = "REVERSE_TO_LONG"
                     elif delta_dir == "SELL" and in_supply and bias == "BEARISH" and cvd_bearish:
                         reversal_type = "REVERSE_TO_SHORT"
                
                # Check rate limit
                if current_time - self.last_signal_time >= self.min_time_between_signals:
                    if reversal_type and current_active_zone:
                         # Calc SL/Labs
                         sl, lots = self._calc_risk(reversal_type, current_active_zone, current_price)
                         signal_object = {
                             "action": reversal_type,
                             "symbol": "XAUUSD",
                             "price": current_price,
                             "sl": sl,
                             "lots": lots,
                             "desc": f"Reversal {self.previous_delta_signal} -> {delta_signal}"
                         }
                    else:
                        # Just Close
                        signal_object = {
                            "action": f"CLOSE_{current_pos_dir}",
                            "symbol": "XAUUSD",
                            "price": current_price,
                            "desc": f"Exit on Delta Reversal {self.previous_delta_signal} -> {delta_signal}"
                        }
                    
                    self.last_signal_time = current_time

        # B. Entry Logic (Triple Filter)
        # Only if no position (and no signal generated yet)
        if (not position_tracker or not position_tracker.has_position()) and not signal_object:
            raw_signal = "WAIT"
            if in_demand and bias == "BULLISH" and cvd_bullish and delta_signal and "BUY" in delta_signal:
                raw_signal = "LONG"
            elif in_supply and bias == "BEARISH" and cvd_bearish and delta_signal and "SELL" in delta_signal:
                raw_signal = "SHORT"
            
            if raw_signal != "WAIT" and current_active_zone:
                 if current_time - self.last_signal_time >= self.min_time_between_signals:
                     sl, lots = self._calc_risk(raw_signal, current_active_zone, current_price)
                     signal_object = {
                         "action": raw_signal,
                         "symbol": "XAUUSD",
                         "price": current_price,
                         "sl": sl,
                         "lots": lots,
                         "desc": f"Triple Filter Entry: {bias} + Zone + {delta_signal}"
                     }
                     self.last_signal_time = current_time

        # Update State
        if delta_signal:
            self.previous_delta_signal = delta_signal
            
        return signal_object

    def _calc_risk(self, signal_type, zone, current_price):
        stop_loss_price = 0.0
        
        if "LONG" in signal_type:
             stop_loss_price = zone["low"] - (self.zone_padding * self.pip_size)
             sl_distance = (current_price - stop_loss_price) / self.pip_size
        elif "SHORT" in signal_type:
             stop_loss_price = zone["high"] + (self.zone_padding * self.pip_size)
             sl_distance = (stop_loss_price - current_price) / self.pip_size
        
        # Safety
        if sl_distance <= 0: sl_distance = 10.0
        
        lots = calculate_lot_size(
            account_balance=self.account_balance,
            stop_loss_pips=sl_distance,
            pip_value_per_lot=self.pip_value
        )
        return stop_loss_price, lots
