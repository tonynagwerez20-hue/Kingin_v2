import logging
import pandas as pd
from typing import Dict, List, Optional
from Engine.base_interfaces import BaseStrategy
from Engine.igof.layers.smc_layers import LayerFactory

logger = logging.getLogger("SMCStrategy")

class SMCStrategy(BaseStrategy):
    """
    Institutional SMC Strategy that uses modular layers to generate trade signals.
    Adheres to the Senior Architect's vision of plug-and-play institutional logic.
    """
    def __init__(self, config: Dict):
        super().__init__(config)
        # Default SMC Layers as per mentorship models
        self.layer_names = config.get("layers", [
            "MechanicalStructure", 
            "LiquiditySweep", 
            "FVGDiscount", 
            "Displacement", 
            "MicroMSS", 
            "KillzoneFilter"
        ])
        
        # Initialize layers via Factory Utility
        self.layers = LayerFactory.create_layers(self.layer_names)
        
        # Strategy Parameters
        self.min_score = config.get("min_total_score", 3.0) # Threshold for aggregate confidence
        self.min_layers = config.get("min_layers_passed", 3) # Minimum confirmation count
        self.symbol = config.get("symbol", "XAUUSD")

    def generate_signal(self, data: Dict) -> Dict:
        """
        Evaluate full SMC context with Hierarchical MTF Routing.
        - H1: Bias/Structure
        - M15: Context/Liquidity/FVG
        - M5/M1: Execution/Displacement/MSS
        """
        h4_df = pd.DataFrame(data.get("h4_candles", []))
        h1_df = pd.DataFrame(data.get("h1_candles", []))
        m15_df = pd.DataFrame(data.get("m15_candles", []))
        m5_df = pd.DataFrame(data.get("m5_candles", []))
        m1_df = pd.DataFrame(data.get("m1_candles", []))

        if m5_df.empty or len(m5_df) < 20:
            return {"action": "NO_TRADE", "reason": "Insufficient M5 data"}

        total_score = 0.0
        details = {}
        passes = 0
        
        # Mapping layers to specific timeframes for institutional accuracy
        timeframe_routing = {
            "KillzoneFilter": m5_df,
            "MechanicalStructure": h4_df if not h4_df.empty else h1_df,
            "LiquiditySweep": m15_df,
            "FVGDiscount": m15_df,
            "MicroMSS": m1_df if not m1_df.empty else m5_df,
            "Displacement": m1_df if not m1_df.empty else m5_df
        }

        # Stage 1: Process layers with routed timeframes
        for layer in self.layers:
            target_df = timeframe_routing.get(layer.name, m5_df)
            
            if target_df.empty or len(target_df) < 5:
                status, score = False, 0.0
            else:
                status, score = layer.validate(target_df)
                
            total_score += score
            if status:
                passes += 1
            details[layer.name] = {"status": status, "score": score}

        # Stage 2: Signal Decision Logic
        # Strategy requires confluence (Multiple layers + High Total Confidence)
        if passes >= self.min_layers and total_score >= self.min_score:
            last_price = m5_df['close'].iloc[-1]
            
            # Simple Directional Bias check (BOS direction or recent momentum)
            # In a more advanced version, this would be linked to the MechanicalStructureLayer state
            is_bullish = m5_df['close'].iloc[-1] > m5_df['close'].iloc[-10]
            direction = "BUY" if is_bullish else "SELL"
            
            # Risk/Reward Management (Targeting 1:2 R:R)
            atr = abs(m5_df['high'] - m5_df['low']).tail(20).mean()
            sl_pips = self.config.get("sl_pips", 50) # Fallback to config pips
            
            # Calculate SL/TP based on ATR or Fixed Pips
            sl_dist = atr * 2 if atr > 0 else (sl_pips * 0.01) # Basic pip math for XAUUSD
            
            sl = last_price - sl_dist if direction == "BUY" else last_price + sl_dist
            tp = last_price + (sl_dist * 2) if direction == "BUY" else last_price - (sl_dist * 2)

            logger.info(f"SMC Strategy Triggered: {direction} @ {last_price} | Score: {total_score:.2f}")

            return {
                "action": "TRADE",
                "direction": direction,
                "symbol": self.symbol,
                "price": last_price,
                "sl": sl,
                "tp": tp,
                "lots": self.config.get("default_lots", 0.01),
                "confidence": total_score / len(self.layers) if self.layers else 0,
                "reason": f"SMC Convergence: {passes} layers passed. Total Confidence: {total_score:.2f}",
                "layer_details": details
            }

        return {
            "action": "NO_TRADE",
            "reason": f"SMC Context Incomplete: {passes}/{len(self.layers)} layers passed. Total Score: {total_score:.2f}",
            "details": details
        }
