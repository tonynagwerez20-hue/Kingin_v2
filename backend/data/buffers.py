"""Data Buffers — Single source of truth."""
from collections import deque
from typing import Dict, Any, List

ohlc_buffers: Dict[str, deque] = {
    "M5": deque(maxlen=500),
    "M15": deque(maxlen=200),
    "H1": deque(maxlen=200),
    "H4": deque(maxlen=200),
    "M1": deque(maxlen=500),
}
tick_buffer = deque(maxlen=10)


def add_candle(timeframe: str, candle: Dict[str, Any]):
    buf = ohlc_buffers.get(timeframe.upper())
    if buf:
        buf.append(candle)


def add_tick(tick: Dict[str, Any]):
    tick_buffer.append(tick)


def get_buffer_counts() -> Dict[str, int]:
    return {tf: len(buf) for tf, buf in ohlc_buffers.items()}


def _standardize_tf(tf: str) -> str:
    mapping = {"H4": "H4", "H1": "H1", "M15": "M15", "M5": "M5", "M1": "M1"}
    return mapping.get(tf.upper(), "M5")


def _candles_from_memory(timeframe: str, limit: int, symbol: str = "XAUUSD") -> List[Dict[str, Any]]:
    tf_key = _standardize_tf(timeframe)
    dq = ohlc_buffers.get(tf_key)
    if dq and len(dq) > 0:
        return list(dq)[-limit:]
    return []