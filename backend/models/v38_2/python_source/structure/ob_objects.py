"""Order-block object and lifecycle states."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

OB_STATES = ("created", "fresh", "touched", "partially_consumed",
             "fully_consumed", "invalidated")


@dataclass
class OrderBlock:
    ob_id: str
    timeframe: str
    direction: str               # "bullish" | "bearish"
    source_candle_bar: int
    source_ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    displacement: float
    displacement_atr: float
    associated_event_id: str
    associated_event_type: str
    freshness: str              # "fresh" | "touched" | "stale"
    mitigation_count: int
    lifecycle: str              # OB_STATES
    creation_bar: int
    creation_ts: pd.Timestamp
    confirmation_bar: int
    confirmation_ts: pd.Timestamp
    upper: float
    lower: float
    midpoint: float
    invalidated: bool = False
    fully_mitigated: bool = False
    first_mitigation_bar: Optional[int] = None
    first_mitigation_ts: Optional[pd.Timestamp] = None
    latest_mitigation_bar: Optional[int] = None
    latest_mitigation_ts: Optional[pd.Timestamp] = None
    full_mitigation_bar: Optional[int] = None
    full_mitigation_ts: Optional[pd.Timestamp] = None
    invalidation_bar: Optional[int] = None
    invalidation_ts: Optional[pd.Timestamp] = None
    deepest_penetration_pct: float = 0.0
    reaction_magnitude: float = 0.0
    quality: float = 0.0
