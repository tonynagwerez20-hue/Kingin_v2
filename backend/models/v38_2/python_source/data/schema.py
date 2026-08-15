"""V38.2 data schema definitions.

Two bar schemas are supported, matching the real files already in the repo:
  - METAQUOTES tab-delimited (<DATE> <TIME> <OPEN> ... <TICKVOL> <SPREAD>)
  - PLAIN CSV (time,open,high,low,close,volume)

The M5/M15 loaders require the MetaQuotes-style (or equivalent) format with
tick_volume + spread. Calendar schema is fixed and matches v38/macro/engine.py.

Spread semantics: the `spread` column may be a numeric OBSERVED spread (e.g.
from a tick feed's bid/ask, or a broker's recorded spread) OR the sentinel
string "UNAVAILABLE" when the source provides no spread information. The
validator distinguishes observed_spread from unavailable_spread rather than
silently inventing a value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Canonical bar column order for normalized V38.2 frames (UTC DatetimeIndex).
BAR_COLUMNS = ["ts", "open", "high", "low", "close", "tick_volume", "spread"]

# Required OHLC bar fields after normalization.
BAR_REQUIRED = {"ts", "open", "high", "low", "close"}

# Sentinel for a source that provides no spread information. Never a fabricated
# number — the validator reports spread_status explicitly.
SPREAD_UNAVAILABLE = "UNAVAILABLE"

# Calendar columns — MUST match v38/macro/engine.py:CALENDAR_COLUMNS exactly.
CALENDAR_COLUMNS = [
    "ts", "country", "currency", "event_name", "category", "importance",
    "actual", "forecast", "previous", "revised_previous", "unit", "directionality",
]

# Timeframe -> pandas resample rule, for gap analysis.
TF_RULES = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h"}


@dataclass(frozen=True)
class BarSchema:
    timeframe: str
    columns: tuple
    has_tick_volume: bool = True
    has_spread: bool = True


BAR_SCHEMAS = {
    "M5": BarSchema("M5", tuple(BAR_COLUMNS)),
    "M15": BarSchema("M15", tuple(BAR_COLUMNS)),
    "H1": BarSchema("H1", tuple(BAR_COLUMNS)),
    "H4": BarSchema("H4", tuple(BAR_COLUMNS)),
}


def expected_bars_per_year(tf: str) -> int:
    """Approximate bar count per year for expectation reporting ONLY.

    Never used to force a target; only to annotate 'expected order of magnitude'
    in the quality report. Assumes ~252 trading days/year, ~24h/day for FX/gold.
    """
    bars_per_day = {"M5": 288, "M15": 96, "H1": 24, "H4": 6}
    return bars_per_day.get(tf, 0) * 252
