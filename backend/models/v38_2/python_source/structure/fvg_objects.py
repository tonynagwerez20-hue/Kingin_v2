"""FVG object and lifecycle states."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

FVG_STATES = ("created", "open", "partially_filled", "fully_filled", "invalidated")


@dataclass
class FairValueGap:
    fvg_id: str
    timeframe: str
    direction: str            # "bullish" | "bearish"
    upper: float
    lower: float
    midpoint: float
    size: float
    size_atr: float
    creation_bar: int
    creation_ts: pd.Timestamp
    confirmation_bar: int
    confirmation_ts: pd.Timestamp
    displacement: float = 0.0
    displacement_atr: float = 0.0
    associated_event_id: str = ""
    associated_event_type: str = ""
    lifecycle: str = "open"
    fill_percentage: float = 0.0
    touches: int = 0
    first_mitigation_bar: Optional[int] = None
    first_mitigation_ts: Optional[pd.Timestamp] = None
    full_fill_bar: Optional[int] = None
    full_fill_ts: Optional[pd.Timestamp] = None
    invalidation_bar: Optional[int] = None
    invalidation_ts: Optional[pd.Timestamp] = None
    fully_filled: bool = False
    invalidated: bool = False
