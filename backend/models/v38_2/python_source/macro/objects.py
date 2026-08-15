"""Macro / news event object model."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import pandas as pd

# Event categories relevant to XAUUSD
EVENT_CATEGORIES = (
    "inflation", "employment", "central_bank", "interest_rate", "gdp",
    "retail_sales", "manufacturing", "services", "consumer_confidence",
    "ppi", "unemployment", "payrolls", "wages", "cb_communication",
    "treasury_yield", "other",
)

# Shock types for the macro interpretation model (NOT a single hard-coded rule)
SHOCK_TYPES = (
    "inflationary", "growth", "labor", "monetary_policy", "risk_safe_haven",
    "neutral",
)

# Gold implication directions
GOLD_IMPLICATIONS = ("bullish", "bearish", "neutral")

# Event states
EVENT_STATES = ("scheduled", "released", "measured", "expired", "suppressed")


@dataclass
class MacroEvent:
    event_id: str
    ts: pd.Timestamp                 # release timestamp (UTC)
    country: str
    currency: str                   # "USD","EUR",...
    event_name: str
    category: str                    # EVENT_CATEGORIES
    importance: int                 # 0..3 (0=low,3=red)
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    revised_previous: Optional[float] = None
    unit: str = ""
    directionality: str = "direct"  # "direct" | "inverse"
    surprise: Optional[float] = None
    surprise_pct: Optional[float] = None
    normalized_surprise: Optional[float] = None
    historical_surprise_z: Optional[float] = None
    shock_type: str = "neutral"
    expected_gold_implication: str = "neutral"
    # measured gold reaction (filled by MacroEngine.measure_reactions)
    reaction: Optional[dict] = None
    reaction_horizons: List[int] = field(default_factory=list)
    vol_before_atr: Optional[float] = None
    vol_after_atr: Optional[float] = None
    state: str = "scheduled"


@dataclass
class CalendarImportResult:
    n_loaded: int
    n_rejected: int
    blocked_reason: str = ""
