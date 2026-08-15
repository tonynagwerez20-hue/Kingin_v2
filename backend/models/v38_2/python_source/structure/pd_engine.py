"""Premium/discount engine based on structural legs (not arbitrary candles).

For each bar, find the most recent confirmed structural leg and compute the
price's position within that leg's high/low range, normalized to [0,1]:

  pos = (price - leg_low) / (leg_high - leg_low)

  pos < 0.5 - band  => discount (favorable for longs)
  pos > 0.5 + band  => premium  (favorable for shorts)
  otherwise          => equilibrium

The leg used must be confirmed before the bar (confirmation_bar <= bar), so no
future structure leaks into the position. Reports: leg high/low, equilibrium,
position, distance from equilibrium (normalized), and the location of OB/FVG/
liquidity relative to the leg.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config
from .objects import StructuralLeg


@dataclass
class PremiumDiscount:
    bar_index: int
    ts: pd.Timestamp
    leg_id: Optional[str]
    leg_high: float
    leg_low: float
    equilibrium: float
    position: float            # [0,1]
    premium_discount: str      # "premium" | "discount" | "equilibrium"
    distance_from_eq: float    # normalized [0,1]


class PremiumDiscountEngine:
    def __init__(self, cfg: V38Config, timeframe: str = "H1"):
        self.cfg = cfg
        self.timeframe = timeframe

    def build_series(self, df: pd.DataFrame, legs: List[StructuralLeg]) -> List[PremiumDiscount]:
        closes = df["close"].to_numpy()
        ts = df["ts"].to_numpy()
        # legs confirmed-by chronological; pick the most recent confirmed leg
        # whose confirmation_bar <= current bar.
        legs_sorted = sorted(legs, key=lambda l: l.confirmation_bar)
        out: List[PremiumDiscount] = []
        li = 0
        last_leg: Optional[StructuralLeg] = None
        band = self.cfg.pd_equilibrium_band
        for b in range(len(df)):
            while li < len(legs_sorted) and legs_sorted[li].confirmation_bar <= b:
                last_leg = legs_sorted[li]
                li += 1
            price = float(closes[b])
            if last_leg is None:
                out.append(PremiumDiscount(b, pd.Timestamp(ts[b]), None, 0.0, 0.0,
                                           0.5, 0.5, "unknown", 0.0))
                continue
            hi, lo = last_leg.high, last_leg.low
            eq = last_leg.equilibrium
            span = hi - lo
            if span <= 0:
                pos = 0.5
            else:
                pos = (price - lo) / span
                pos = max(0.0, min(1.0, pos))
            if pos > 0.5 + band:
                pd_label = "premium"
            elif pos < 0.5 - band:
                pd_label = "discount"
            else:
                pd_label = "equilibrium"
            dist_eq = abs(pos - 0.5) * 2.0
            out.append(PremiumDiscount(b, pd.Timestamp(ts[b]), last_leg.leg_id,
                                       float(hi), float(lo), float(eq),
                                       float(pos), pd_label, float(dist_eq)))
        return out
