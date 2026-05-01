import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import time
import json
from pathlib import Path
from .layers import (
    SessionFilterLayer, H1StructuralBiasLayer, ZoneQualityLayer,
    LiquidityEventLayer, MicrostructureShiftLayer, DisplacementLayer
)

class V1FiltrationEngine:
    """
    Modular Filtration Engine that orchestrates multiple plug-and-play layers.
    """
    def __init__(self, config_path: Optional[str] = None, layers: Optional[List] = None):
        """
        Initialize the engine with configuration and layers.
        
        Args:
            config_path: Path to trading_params.json
            layers: List of FiltrationLayer instances. If None, initializes default layers.
        """
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "trading_params.json"
        
        with open(config_path, 'r') as f:
            self.full_config = json.load(f)
        
        self.config = self.full_config.get("igof_v1", {})
        self.session_config = self.full_config.get("session_filter", {})
        
        # Initialize layers if not provided
        if layers is not None:
            self.layers = layers
        else:
            self.layers = [
                SessionFilterLayer(self.session_config),
                H1StructuralBiasLayer(self.config.get("layer1_h1_bias", {})),
                ZoneQualityLayer(self.config.get("layer2_zone_quality", {})),
                LiquidityEventLayer(self.config.get("layer3_liquidity", {})),
                MicrostructureShiftLayer(self.config.get("layer4_microstructure", {})),
                DisplacementLayer(self.config.get("layer5_displacement", {})),
                MLFilterLayer(self.config.get("layer6_ml", {}))
            ]

    def process_all_layers(self, market_snapshot: Dict) -> Dict:
        """
        Execute ALL registered layers sequentially. 
        Returns NO_TRADE if any layer fails.
        """
        results = []
        
        # Ensure current_time is available for layers that need it
        if "current_time" not in market_snapshot and "m5_candles" in market_snapshot:
            if market_snapshot["m5_candles"]:
                market_snapshot["current_time"] = market_snapshot["m5_candles"][-1].get("time")

        for layer in self.layers:
            res = layer.process(market_snapshot)
            results.append(res)
            
            if not res.get("status", False):
                return {
                    "action": "NO_TRADE", 
                    "reason": f"{layer.__class__.__name__}: {res.get('reason', 'Filtered')}",
                    "layer_results": results
                }
        
        return {
            "action": "TRADE_ALLOWED", 
            "reason": "All Layers Passed", 
            "layer_results": results
        }

    def calculate_stop_loss(self, m5_candles: List[Dict], direction: str) -> Optional[float]:
        """
        Execution helper: Calculate Stop Loss placement (2 pips below/above liquidity event).
        Kept for backward compatibility with main_loop/execution logic.
        """
        if len(m5_candles) < 10:
            return None
        
        # Use layer3 config for sweep lookback
        l3_config = self.config.get("layer3_liquidity", {})
        lookback = l3_config.get('sweep_lookback_candles', 5)
        
        prev_min = min(c['low'] for c in m5_candles[-(lookback+1):-1])
        prev_max = max(c['high'] for c in m5_candles[-(lookback+1):-1])
        
        # SL buffer (default 2 pips = 0.02 for Gold)
        sl_buffer = 0.02 
        
        if direction == "LONG":
            return prev_min - sl_buffer
        elif direction == "SHORT":
            return prev_max + sl_buffer
        
        return None
