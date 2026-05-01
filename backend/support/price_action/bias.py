from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# ensure project root is on path for imports if run directly
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from data_feed.dispatcher import ohlc_buffers
except (ImportError, ModuleNotFoundError):
    ohlc_buffers = {}

def calculate_structure_bias(candles: List[Dict]) -> str:
    """
    Determine market bias based on Market Structure (Higher Highs/Lows).
    Returns: "BULLISH", "BEARISH", or "RANGE"
    """
    if not candles or len(candles) < 10:
        return "RANGE"
    
    # Simple Fractal / Swing Detection
    swing_highs = []
    swing_lows = []
    
    for i in range(1, len(candles) - 1):
        prev = candles[i-1]
        curr = candles[i]
        next_c = candles[i+1]
        
        if curr["high"] > prev["high"] and curr["high"] > next_c["high"]:
            swing_highs.append({"val": curr["high"], "idx": i})
            
        if curr["low"] < prev["low"] and curr["low"] < next_c["low"]:
            swing_lows.append({"val": curr["low"], "idx": i})
            
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "RANGE"
        
    last_h = swing_highs[-1]
    prev_h = swing_highs[-2]
    last_l = swing_lows[-1]
    prev_l = swing_lows[-2]
    
    hh = last_h["val"] > prev_h["val"]
    lh_market = last_h["val"] < prev_h["val"]
    hl = last_l["val"] > prev_l["val"]
    ll_market = last_l["val"] < prev_l["val"]
    
    if hh and hl:
        return "BULLISH"
    if lh_market and ll_market:
        return "BEARISH"
        
    return "RANGE"
