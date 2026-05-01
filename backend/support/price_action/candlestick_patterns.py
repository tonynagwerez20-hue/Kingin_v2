import pandas as pd
from typing import Dict, List, Optional

def get_candle_body_size(candle: Dict) -> float:
    return abs(candle['open'] - candle['close'])

def get_candle_wick_top(candle: Dict) -> float:
    return candle['high'] - max(candle['open'], candle['close'])

def get_candle_wick_bottom(candle: Dict) -> float:
    return min(candle['open'], candle['close']) - candle['low']

def is_bullish(candle: Dict) -> bool:
    return candle['close'] > candle['open']

def is_bearish(candle: Dict) -> bool:
    return candle['close'] < candle['open']

def recognize_patterns(candles: List[Dict]) -> List[str]:
    """Recognizes candlestick patterns from the last few candles."""
    if len(candles) < 3:
        return []
        
    patterns = []
    c1 = candles[-1] # Current (forming or just closed)
    c2 = candles[-2] # Previous
    c3 = candles[-3] # Previous previous
    
    # 1. HAMMER (Bullish)
    body_size = get_candle_body_size(c1)
    bottom_wick = get_candle_wick_bottom(c1)
    top_wick = get_candle_wick_top(c1)
    if bottom_wick > (body_size * 2) and top_wick < (body_size * 0.5):
        patterns.append("HAMMER")
        
    # 2. SHOOTING STAR (Bearish)
    if top_wick > (body_size * 2) and bottom_wick < (body_size * 0.5):
        patterns.append("SHOOTING_STAR")
        
    # 3. BULLISH ENGULFING
    if is_bearish(c2) and is_bullish(c1) and \
       c1['open'] <= c2['close'] and c1['close'] > c2['open']:
        patterns.append("BULLISH_ENGULFING")
        
    # 4. BEARISH ENGULFING
    if is_bullish(c2) and is_bearish(c1) and \
       c1['open'] >= c2['close'] and c1['close'] < c2['open']:
        patterns.append("BEARISH_ENGULFING")
        
    # 5. MORNING STAR (Bullish)
    if is_bearish(c3) and get_candle_body_size(c2) < (get_candle_body_size(c3) * 0.3) and is_bullish(c1):
        patterns.append("MORNING_STAR")
        
    # 6. EVENING STAR (Bearish)
    if is_bullish(c3) and get_candle_body_size(c2) < (get_candle_body_size(c3) * 0.3) and is_bearish(c1):
        patterns.append("EVENING_STAR")

    # 7. DOJI
    if body_size < (abs(c1['high'] - c1['low']) * 0.1):
        patterns.append("DOJI")

    return patterns

def get_candlestick_signal(candles: List[Dict]) -> Optional[str]:
    """Returns 'BUY', 'SELL', or None based on recognized patterns."""
    patterns = recognize_patterns(candles)
    
    bullish_patterns = ["HAMMER", "BULLISH_ENGULFING", "MORNING_STAR"]
    bearish_patterns = ["SHOOTING_STAR", "BEARISH_ENGULFING", "EVENING_STAR"]
    
    if any(p in patterns for p in bullish_patterns):
        return "BUY"
    if any(p in patterns for p in bearish_patterns):
        return "SELL"
        
    return None
