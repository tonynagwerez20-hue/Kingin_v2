"""Structural object models shared across the structure engine.

All objects carry a stable ID, a `bar_index`/`ts` for the bar at which they
became *usable* (confirmation), and a lifecycle status. The
`confirmation_bar`/`confirmation_ts` is the earliest bar at which downstream
features are permitted to read the object — this is the leakage boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

import pandas as pd

# Lifecycle enums ------------------------------------------------------------
BOS_STATES = ("detected", "confirmed", "retested", "invalidated")
OB_STATES = ("created", "fresh", "touched", "partially_consumed",
             "fully_consumed", "invalidated")
FVG_STATES = ("created", "open", "partially_filled", "fully_filled", "invalidated")
LIQ_STATES = ("identified", "strengthened", "swept", "reclaimed", "invalidated")
REGIMES = ("bullish", "bearish", "neutral")


@dataclass
class StructuralEvent:
    event_id: str
    symbol: str
    timeframe: str
    ts: pd.Timestamp
    bar_index: int
    event_type: str          # "BOS" | "CHOCH"
    direction: str           # "bullish" | "bearish"
    originating_swing_id: str
    broken_level: float
    break_price: float
    confirmation_price: float
    displacement: float       # raw price move that constituted the break
    displacement_atr: float  # ATR-normalized displacement
    structural_leg_id: Optional[str] = None
    parent_structure_id: Optional[str] = None
    protected_level_id: Optional[str] = None
    quality: float = 0.0
    invalidation_level: Optional[float] = None
    lifecycle: str = "confirmed"   # BOS_STATES
    retest_bar: Optional[int] = None
    retest_price: Optional[float] = None
    continuation_bar: Optional[int] = None
    confirmation_bar: int = 0
    confirmation_ts: Optional[pd.Timestamp] = None


@dataclass
class StructuralLeg:
    """A directional leg between two external swings."""
    leg_id: str
    timeframe: str
    direction: str            # "bullish" | "bearish"
    start_swing_id: str
    end_swing_id: str
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    start_bar: int
    end_bar: int
    start_price: float
    end_price: float
    high: float
    low: float
    equilibrium: float
    parent_leg_id: Optional[str] = None
    confirmation_bar: int = 0
    confirmation_ts: Optional[pd.Timestamp] = None


@dataclass
class ProtectedLevel:
    protected_id: str
    kind: str                 # "high" | "low"
    price: float
    swing_id: str
    protecting_event_id: str  # the BOS/CHOCH that protects it
    ts: pd.Timestamp
    bar_index: int
    status: str = "active"    # "active" | "broken"
    break_ts: Optional[pd.Timestamp] = None
    replacement_id: Optional[str] = None
    confirmation_bar: int = 0
    confirmation_ts: Optional[pd.Timestamp] = None
