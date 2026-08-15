"""Deterministic swing-point engine — the foundation of V38 structure.

A swing is a *confirmed* pivot, never a look-ahead-free guess. Detection and
confirmation are separated:

  detection_ts   : the bar at which the pivot would be *suspected* (the pivot
                   bar itself, whose extreme is the candidate).
  confirmation_ts : the bar at which enough subsequent bars have printed to
                   *confirm* the pivot (k strictly-lower/higher bars on each
                   side). Features may only use a swing once
                   `confirmation_ts <= entry_ts`.

Implementation: fractal pivots with strength `k` (k bars on each side whose
high/low are strictly less/greater than the candidate). External vs internal
classification is derived afterward from the sequence of confirmed swings:
external = a high higher than the previous two highs / low lower than the
previous two lows; otherwise internal. This is the standard SMC definition and
is fully deterministic.

Protected highs/lows are derived here too: the most recent external swing of
each polarity whose break would constitute a CHOCH candidate. They are
recomputed from structure (see structure engine) but the *candidate* protected
levels are the latest external pivots; the structure engine promotes/breaks
them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config
from ..bars import atr


@dataclass
class Swing:
    swing_id: str
    bar_index: int            # index into the source DataFrame
    ts: pd.Timestamp          # the pivot bar's timestamp (detection)
    price: float
    kind: str                 # "high" | "low"
    strength: int              # fractal strength k
    confirmation_bar: int     # bar index where confirmation completed
    confirmation_ts: pd.Timestamp
    external: bool            # external (structural) vs internal
    atr_at_confirmation: float


class SwingEngine:
    def __init__(self, cfg: V38Config):
        self.cfg = cfg

    def detect(self, df: pd.DataFrame) -> List[Swing]:
        k = self.cfg.swing_strength
        n = len(df)
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        ts = df["ts"].to_numpy()
        atr_arr = atr(df, self.cfg.displacement_atr_period)

        raw: List[Swing] = []
        # A pivot at index i is confirmed at index i+k (needs k bars after).
        # Precompute true-range so ATR is never NaN (even before the Wilder
        # warmup period) — robustness for the earliest swings.
        prev_close = np.empty(n)
        prev_close[0] = df["close"].to_numpy()[0]
        prev_close[1:] = df["close"].to_numpy()[:-1]
        tr = np.maximum.reduce([
            df["high"].to_numpy() - df["low"].to_numpy(),
            np.abs(df["high"].to_numpy() - prev_close),
            np.abs(df["low"].to_numpy() - prev_close),
        ])
        for i in range(k, n - k):
            hh = highs[i]
            ll = lows[i]
            left_highs = highs[i - k:i]
            right_highs = highs[i + 1:i + 1 + k]
            left_lows = lows[i - k:i]
            right_lows = lows[i + 1:i + 1 + k]

            is_high = (np.all(left_highs < hh) and np.all(right_highs < hh))
            is_low = (np.all(left_lows > ll) and np.all(right_lows > ll))
            if not (is_high or is_low):
                continue

            kind = "high" if is_high else "low"
            conf_idx = i + k
            conf_ts = pd.Timestamp(ts[conf_idx])
            pivot_ts = pd.Timestamp(ts[i])
            atr_conf = float(atr_arr[conf_idx])
            if np.isnan(atr_conf):
                atr_conf = float(tr[conf_idx])  # robust fallback before warmup
            raw.append(Swing(
                swing_id=f"SW{i}_{kind[:1]}",
                bar_index=i, ts=pivot_ts, price=float(hh if is_high else ll),
                kind=kind, strength=k,
                confirmation_bar=conf_idx, confirmation_ts=conf_ts,
                external=False, atr_at_confirmation=atr_conf,
            ))

        # Enforce min spacing: keep the most extreme of any two adjacent
        # same-kind pivots closer than swing_min_spacing bars.
        raw = self._enforce_spacing(raw)

        # Classify external vs internal deterministically.
        self._classify_external(raw)
        return raw

    def _enforce_spacing(self, swings: List[Swing]) -> List[Swing]:
        spacing = self.cfg.swing_min_spacing
        if spacing <= 1:
            return swings
        kept: List[Swing] = []
        last_by_kind = {"high": -10**9, "low": -10**9}
        for s in swings:
            if s.bar_index - last_by_kind[s.kind] < spacing:
                prev = kept[-1]
                if prev.kind == s.kind:
                    replace = ((s.kind == "high" and s.price > prev.price) or
                               (s.kind == "low" and s.price < prev.price))
                    if replace:
                        kept[-1] = s
                        last_by_kind[s.kind] = s.bar_index
                    continue
            kept.append(s)
            last_by_kind[s.kind] = s.bar_index
        return kept

    @staticmethod
    def _classify_external(swings: List[Swing]) -> None:
        """Mark a high external if higher than the previous two confirmed
        highs; a low external if lower than the previous two confirmed lows.
        Otherwise internal."""
        prev_h: List[Swing] = []
        prev_l: List[Swing] = []
        for s in swings:
            if s.kind == "high":
                s.external = (len(prev_h) >= 2 and
                              s.price > max(p.price for p in prev_h[-2:]))
                prev_h.append(s)
            else:
                s.external = (len(prev_l) >= 2 and
                              s.price < min(p.price for p in prev_l[-2:]))
                prev_l.append(s)


def detect_swings(df: pd.DataFrame, cfg: V38Config) -> List[Swing]:
    """Public entry: detect + classify external swings deterministically."""
    engine = SwingEngine(cfg)
    swings = engine.detect(df)
    SwingEngine._classify_external(swings)
    return swings

