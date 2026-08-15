"""FVG (Fair Value Gap) lifecycle engine.

A bullish FVG: gap up — low[i] > high[i-2]  (imbalance between candle i-2 and i,
with i-1 as the displacement candle). Bearish FVG: high[i] < low[i-2].

Minimum size filter: |gap| >= fvg_min_size_atr * ATR to reject noise.

Lifecycle:
  created -> open -> partially_filled -> fully_filled -> invalidated

  * created/open: gap exists, unfilled.
  * touched/partially_filled: a later bar's wick enters the gap (0%<fill<100%).
  * fully_filled: a later bar closes back through the origin boundary.
  * invalidated: price closed through in the direction that erases the gap
    beyond the far boundary (gap fully consumed and reversed past it).

Each FVG records boundaries, midpoint, fill %, first/full mitigation bars,
associated displacement & event where one exists, confirmation_bar (= the bar
that created the gap, index i — at close of i the gap is fully known).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config
from ..bars import atr
from .fvg_objects import FairValueGap
from .objects import StructuralEvent


class FVGEngine:
    def __init__(self, cfg: V38Config, symbol: str = "XAUUSD", timeframe: str = "H1"):
        self.cfg = cfg
        self.symbol = symbol
        self.timeframe = timeframe

    def build(self, df: pd.DataFrame, events: List[StructuralEvent]) -> List[FairValueGap]:
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        ts = df["ts"].to_numpy()
        n = len(df)
        atr_arr = atr(df, self.cfg.displacement_atr_period)
        prev_close = np.empty(n)
        prev_close[0] = closes[0]
        prev_close[1:] = closes[:-1]
        tr = np.maximum.reduce([
            highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close),
        ])
        atr_safe = np.where(np.isnan(atr_arr), tr, atr_arr)

        min_atr = self.cfg.fvg_min_size_atr
        ev_by_bar = {e.bar_index: e for e in events}
        fvgs: List[FairValueGap] = []
        counter = 0
        for i in range(2, n):
            a = atr_safe[i] if atr_safe[i] > 0 else 1.0
            # bullish gap: low[i] > high[i-2]
            if lows[i] > highs[i - 2]:
                size = lows[i] - highs[i - 2]
                if size >= min_atr * a:
                    counter += 1
                    upper, lower = float(lows[i]), float(highs[i - 2])
                    ev = ev_by_bar.get(i)
                    fvgs.append(FairValueGap(
                        fvg_id=f"FVG{counter}_{self.timeframe}",
                        timeframe=self.timeframe, direction="bullish",
                        upper=upper, lower=lower, midpoint=(upper + lower) / 2.0,
                        size=float(size), size_atr=float(size / a),
                        creation_bar=i, creation_ts=pd.Timestamp(ts[i]),
                        confirmation_bar=i, confirmation_ts=pd.Timestamp(ts[i]),
                        displacement=ev.displacement if ev else 0.0,
                        displacement_atr=ev.displacement_atr if ev else float(size / a),
                        associated_event_id=ev.event_id if ev else "",
                        associated_event_type=ev.event_type if ev else "",
                    ))
            # bearish gap: high[i] < low[i-2]
            elif highs[i] < lows[i - 2]:
                size = lows[i - 2] - highs[i]
                if size >= min_atr * a:
                    counter += 1
                    upper, lower = float(lows[i - 2]), float(highs[i])
                    ev = ev_by_bar.get(i)
                    fvgs.append(FairValueGap(
                        fvg_id=f"FVG{counter}_{self.timeframe}",
                        timeframe=self.timeframe, direction="bearish",
                        upper=upper, lower=lower, midpoint=(upper + lower) / 2.0,
                        size=float(size), size_atr=float(size / a),
                        creation_bar=i, creation_ts=pd.Timestamp(ts[i]),
                        confirmation_bar=i, confirmation_ts=pd.Timestamp(ts[i]),
                        displacement=ev.displacement if ev else 0.0,
                        displacement_atr=ev.displacement_atr if ev else float(size / a),
                        associated_event_id=ev.event_id if ev else "",
                        associated_event_type=ev.event_type if ev else "",
                    ))
        self._track_fill(fvgs, highs, lows, closes, ts)
        return fvgs

    def _track_fill(self, fvgs: List[FairValueGap], highs, lows, closes, ts) -> None:
        n = len(closes)
        for f in fvgs:
            span = f.upper - f.lower
            if span <= 0:
                f.lifecycle = "invalidated"
                f.invalidated = True
                continue
            first = True
            for b in range(f.creation_bar + 1, n):
                bh, bl, bc = highs[b], lows[b], closes[b]
                entered = (bh >= f.lower and bl <= f.upper)
                if entered:
                    if first:
                        f.first_mitigation_bar = b
                        f.first_mitigation_ts = pd.Timestamp(ts[b])
                        f.lifecycle = "partially_filled"
                        first = False
                    # fill percentage: how much of the gap has been traded through
                    if f.direction == "bullish":
                        filled = (f.upper - max(f.lower, bl)) if bl < f.upper else 0.0
                    else:
                        filled = (min(f.upper, bh) - f.lower) if bh > f.lower else 0.0
                    pct = max(0.0, min(1.0, filled / span))
                    f.fill_percentage = max(f.fill_percentage, float(pct))
                    if pct >= 1.0 and not f.fully_filled:
                        f.lifecycle = "fully_filled"
                        f.fully_filled = True
                        f.full_fill_bar = b
                        f.full_fill_ts = pd.Timestamp(ts[b])
                    # invalidation: close through origin in opposite direction
                    if f.direction == "bullish" and bc < f.lower:
                        f.lifecycle = "invalidated"
                        f.invalidated = True
                        f.invalidation_bar = b
                        f.invalidation_ts = pd.Timestamp(ts[b])
                        break
                    if f.direction == "bearish" and bc > f.upper:
                        f.lifecycle = "invalidated"
                        f.invalidated = True
                        f.invalidation_bar = b
                        f.invalidation_ts = pd.Timestamp(ts[b])
                        break
            f.touches = 0 if first else 1
