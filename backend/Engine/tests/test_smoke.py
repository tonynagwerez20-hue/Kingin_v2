"""Simple smoke test to verify aggregator imports and runs inside the project venv."""
import sys
from pathlib import Path

# Add project root to path so imports work from tests folder
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.Aggregator import ohlc_buffers, aggregate_candles

# Prepare mock M5 candles (3 candles -> 1 M15)
mock = [
    {"open": 1000, "high": 1005, "low": 999, "close": 1002, "time": None},
    {"open": 1002, "high": 1010, "low": 1001, "close": 1008, "time": None},
    {"open": 1008, "high": 1012, "low": 1006, "close": 1009, "time": None},
]

buffers = {"M5": mock, "M15": [], "H1": []}
agg = aggregate_candles("M5", "M15", 3, buffers=buffers, align=False)
print("Aggregated:", agg)
