"""Liquidity, equal-level, and inducement object models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd

LIQ_STATES = ("identified", "strengthened", "swept", "reclaimed", "invalidated")


@dataclass
class LiquidityPool:
    pool_id: str
    type: str                # "high" | "low"
    price: float
    creation_ts: pd.Timestamp
    creation_bar: int
    source_swings: List[str]
    touches: int
    strength: float
    confirmation_bar: int
    confirmation_ts: pd.Timestamp
    swept: bool = False
    sweep_bar: Optional[int] = None
    sweep_ts: Optional[pd.Timestamp] = None
    sweep_depth_atr: float = 0.0
    post_sweep_reaction_atr: float = 0.0
    invalidated: bool = False


@dataclass
class EqualLevel:
    equal_id: str
    type: str                 # "high" | "low"
    first_bar: int
    first_ts: pd.Timestamp
    first_price: float
    second_bar: int
    second_ts: pd.Timestamp
    second_price: float
    price_diff: float
    normalized_diff: float       # in ATR units
    num_equal: int
    confirmation_bar: int
    confirmation_ts: pd.Timestamp
    swept: bool = False


@dataclass
class Inducement:
    inducement_id: str
    parent_leg_id: str
    inducement_swing_id: str
    inducement_price: float
    intended_liquidity: float
    creation_ts: pd.Timestamp
    creation_bar: int
    confirmation_bar: int
    confirmation_ts: pd.Timestamp
    swept: bool = False
