from typing import Dict, List, Any, Optional
from support.strategies.base_strategy import AbstractStrategy

class StrategyManager:
    def __init__(self, strategies: List[AbstractStrategy]):
        self.strategies = strategies

    def aggregate_signals(self, htf_buffer: List[Dict], mtf_buffer: List[Dict], ltf_buffer: List[Dict], **kwargs) -> Optional[Dict]:
        """
        Implements the 'Triple-TF Filtration & Trigger' architecture:
        1. HTF Filter (H1 Bias): Defines the structural trend (FilterOne).
        2. MTF Filter (M15 Zone): Validates supply/demand context (FilterTwo).
        3. LTF Trigger (M5 Delta/Candle): High-precision entry execution (CandlestickStrategy).
        
        Strict Alignment Rule: Entries are only permitted when all three layers (H1, M15, M5) 
        synchronize in direction. Exits are triggered by a reversal in any layer.
        """
        from support.strategies.filter_one import FilterOne
        from support.strategies.filter_two import FilterTwo
        from support.strategies.candlestick_trigger import CandlestickStrategy

        f1 = next((s for s in self.strategies if isinstance(s, FilterOne)), None)
        f2 = next((s for s in self.strategies if isinstance(s, FilterTwo)), None)
        candlestick_strat = next((s for s in self.strategies if isinstance(s, CandlestickStrategy)), None)
        
        if not f1 or not f2 or not candlestick_strat:
            return None
        
        # --- 2. Exit Logic (Evaluate all filters against current position) ---
        position_tracker = kwargs.get("position_tracker")
        if position_tracker and position_tracker.has_position():
            curr_pos_dir = position_tracker.get_position_direction()
            exit_reasons = []

            # A. Check Bias Filter (H1) - Filter One
            bias_res = f1.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
            if bias_res:
                if (curr_pos_dir == "LONG" and bias_res["action"] == "SHORT") or \
                   (curr_pos_dir == "SHORT" and bias_res["action"] == "LONG"):
                    exit_reasons.append("Bias Reversal (H1)")

            # B. Check Zone Filter (M15) - Filter Two
            zone_res = f2.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
            if zone_res:
                if (curr_pos_dir == "LONG" and zone_res["action"] == "SHORT") or \
                   (curr_pos_dir == "SHORT" and zone_res["action"] == "LONG"):
                   exit_reasons.append(f"Opposite Zone Reached ({zone_res['desc']})")

            # C. Check Trigger Strategy (Delta/Candle) - Final Trigger
            from support.strategies.orderflow import OrderflowStrategy
            of_strat = next((s for s in self.strategies if isinstance(s, OrderflowStrategy)), candlestick_strat)
            trigger_res = of_strat.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
            if trigger_res:
                if (curr_pos_dir == "LONG" and trigger_res["action"] == "SHORT") or \
                   (curr_pos_dir == "SHORT" and trigger_res["action"] == "LONG"):
                    exit_reasons.append("Trigger Reversal (Orderflow/Candle)")

            if exit_reasons:
                return {
                    "action": f"CLOSE_{curr_pos_dir}",
                    "symbol": "XAUUSD",
                    "price": ltf_buffer[-1]["close"] if ltf_buffer else 0,
                    "desc": f"TRIPLE EXIT: {', '.join(exit_reasons)}",
                    "confidence": 1.0
                }

        # --- 3. Entry Logic (All filters must align) ---
        f1_res = f1.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
        if not f1_res:
            if kwargs.get("verbose_logs", True): print("[Strategy] WAIT: Filter 1 (H1 Bias) not met")
            return None

        f2_res = f2.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
        if not f2_res:
             if kwargs.get("verbose_logs", True): print("[Strategy] WAIT: Filter 2 (M15 Zone) not met")
             return None
        
        # Inject zone for Trigger
        if f2_res and "active_zone" in f2_res:
            kwargs["active_zone"] = f2_res["active_zone"]
            
        trigger_signal = candlestick_strat.evaluate(htf_buffer, mtf_buffer, ltf_buffer, **kwargs)
        
        if not trigger_signal:
            if kwargs.get("verbose_logs", True): print("[Strategy] WAIT: Trigger (M5 Candlestick) not met")
            return None

        if f1_res and f2_res and trigger_signal:
            if f1_res["action"] == f2_res["action"] == trigger_signal["action"]:
                final_sig = trigger_signal.copy()
                final_sig["desc"] = f"TRIPLE ENTRY: {f1_res['desc']} + {f2_res['desc']} + Trigger confirmed"
                return final_sig
            else:
                if kwargs.get("verbose_logs", True): 
                    print(f"[Strategy] WAIT: Directions MISALIGNED - F1:{f1_res['action']} F2:{f2_res['action']} Trig:{trigger_signal['action']}")
        
        return None
