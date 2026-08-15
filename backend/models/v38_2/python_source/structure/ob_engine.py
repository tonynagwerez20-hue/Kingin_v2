"""Order-block engine with full mitigation lifecycle.

An OB is NOT "any opposite-colour candle". It is the last opposite-polarity
candle that preceded a structural break (BOS/CHOCH) with displacement. This is
the deterministic SMC definition and is fully reproducible.

Lifecycle:
  created -> fresh -> touched -> partially_consumed -> fully_consumed -> invalidated

  * created/fresh: identified from the displacement move that broke structure.
  * touched:        a later bar's wick enters the OB zone (high/low overlap).
  * partially_consumed: wick penetration > 0% but the opposite boundary still
                     intact and price did not close through.
  * fully_consumed:  price closed through the far boundary (full mitigation).
  * invalidated:    closed through in the *opposite* direction (OB failed) OR
                    exceeded ob_max_age_bars untouched.

Each OB records: source candle, displacement, associated BOS/CHOCH, mitigation
count, first/latest mitigation, deepest penetration %, reaction magnitude,
and confirmation_bar (the bar at which the OB itself became valid — the bar of
the displacement break, not earlier).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config
from .objects import StructuralEvent
from .ob_objects import OrderBlock, OB_STATES


@dataclass
class _Pending:
    """A candle waiting to be promoted to OB if a break follows."""
    bar_index: int
    ts: pd.Timestamp
    direction: str          # "bullish" if down-candle before up-break, else "bearish"
    open: float
    high: float
    low: float
    close: float


class OrderBlockEngine:
    def __init__(self, cfg: V38Config, symbol: str = "XAUUSD", timeframe: str = "H1"):
        self.cfg = cfg
        self.symbol = symbol
        self.timeframe = timeframe

    def build(self, df: pd.DataFrame, events: List[StructuralEvent]) -> List[OrderBlock]:
        opens = df["open"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        ts = df["ts"].to_numpy()
        n = len(df)

        # Precompute ATR-like displacement per bar via True Range.
        prev_close = np.empty(n)
        prev_close[0] = closes[0]
        prev_close[1:] = closes[:-1]
        tr = np.maximum.reduce([
            highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close),
        ])

        # Map each structural event to its bar for quick lookup.
        ev_by_bar = {e.bar_index: e for e in events}

        obs: List[OrderBlock] = []
        # Keep a short window of opposite-polarity candles preceding a break.
        # An OB candidate = the most recent opposite-colour candle before a
        # displacement break. We scan events (already chronological) and look
        # back a few bars for the last opposite candle.
        counter = 0
        for ev in events:
            b = ev.bar_index
            # displacement break: the candle at b is the break candle.
            # For a bullish break the OB is the last down-candle at/before b-1.
            # For a bearish break the OB is the last up-candle at/before b-1.
            lookback = max(1, self.cfg.swing_strength + 1)
            start = max(0, b - lookback)
            ob_candle_idx: Optional[int] = None
            if ev.direction == "bullish":
                for j in range(b - 1, start - 1, -1):
                    if closes[j] < opens[j]:  # down candle
                        ob_candle_idx = j
                        break
            else:
                for j in range(b - 1, start - 1, -1):
                    if closes[j] > opens[j]:  # up candle
                        ob_candle_idx = j
                        break
            if ob_candle_idx is None:
                continue

            counter += 1
            o, h, l, c = (opens[ob_candle_idx], highs[ob_candle_idx],
                          lows[ob_candle_idx], closes[ob_candle_idx])
            ob_dir = "bullish" if ev.direction == "bullish" else "bearish"
            disp = ev.displacement
            disp_atr = ev.displacement_atr
            # OB zone: high-low of the source candle.
            ob = OrderBlock(
                ob_id=f"OB{counter}_{self.timeframe}",
                timeframe=self.timeframe, direction=ob_dir,
                source_candle_bar=ob_candle_idx,
                source_ts=pd.Timestamp(ts[ob_candle_idx]),
                open=float(o), high=float(h), low=float(l), close=float(c),
                displacement=disp, displacement_atr=disp_atr,
                associated_event_id=ev.event_id,
                associated_event_type=ev.event_type,
                freshness="fresh",
                mitigation_count=0,
                lifecycle="fresh",
                creation_bar=b,  # valid only once the break confirms it
                creation_ts=pd.Timestamp(ts[b]),
                confirmation_bar=b,
                confirmation_ts=pd.Timestamp(ts[b]),
                upper=float(h), lower=float(l),
                midpoint=float((h + l) / 2.0),
                invalidated=False, fully_mitigated=False,
                quality=min(1.0, disp_atr / (self.cfg.choch_min_atr_mult * 3)),
            )
            obs.append(ob)

        # Track mitigation lifecycle forward from each OB's confirmation bar.
        self._track_mitigation(obs, highs, lows, closes, ts, tr)
        return obs

    def _track_mitigation(self, obs: List[OrderBlock], highs, lows, closes, ts, tr) -> None:
        n = len(closes)
        age_limit = self.cfg.ob_max_age_bars
        for ob in obs:
            zone_high = ob.high
            zone_low = ob.low
            depth = zone_high - zone_low
            if depth <= 0:
                ob.lifecycle = "invalidated"
                ob.invalidated = True
                continue
            first_touch = True
            deepest = 0.0
            for b in range(ob.confirmation_bar + 1, min(n, ob.confirmation_bar + 1 + age_limit)):
                bh, bl, bc = highs[b], lows[b], closes[b]
                entered = (bh >= zone_low and bl <= zone_high)
                if entered:
                    if first_touch:
                        ob.first_mitigation_bar = b
                        ob.first_mitigation_ts = pd.Timestamp(ts[b])
                        ob.freshness = "touched"
                        ob.lifecycle = "touched"
                        first_touch = False
                    ob.mitigation_count += 1
                    # penetration depth: how far the wick penetrated the zone
                    if ob.direction == "bullish":
                        pen = max(0.0, (bh - zone_low)) / depth
                    else:
                        pen = max(0.0, (zone_high - bl)) / depth
                    deepest = max(deepest, pen)
                    ob.latest_mitigation_bar = b
                    ob.latest_mitigation_ts = pd.Timestamp(ts[b])
                    # reaction magnitude (how far price bounced off OB)
                    if ob.direction == "bullish":
                        react = bc - bl
                    else:
                        react = bh - bc
                    ob.reaction_magnitude = max(ob.reaction_magnitude, float(react))
                    # full mitigation: close through the far boundary
                    if self.cfg.ob_close_through_invalidates:
                        if ob.direction == "bullish" and bc < zone_low:
                            ob.lifecycle = "fully_consumed"
                            ob.fully_mitigated = True
                            ob.full_mitigation_bar = b
                            ob.full_mitigation_ts = pd.Timestamp(ts[b])
                            break
                        if ob.direction == "bearish" and bc > zone_high:
                            ob.lifecycle = "fully_consumed"
                            ob.fully_mitigated = True
                            ob.full_mitigation_bar = b
                            ob.full_mitigation_ts = pd.Timestamp(ts[b])
                            break
                    if deepest > 0.5 and not ob.fully_mitigated:
                        ob.lifecycle = "partially_consumed"
                # invalidation: close through in the opposite direction
                if ob.direction == "bullish" and bc > zone_high:
                    ob.lifecycle = "invalidated"
                    ob.invalidated = True
                    ob.invalidation_bar = b
                    ob.invalidation_ts = pd.Timestamp(ts[b])
                    break
                if ob.direction == "bearish" and bc < zone_low:
                    ob.lifecycle = "invalidated"
                    ob.invalidated = True
                    ob.invalidation_bar = b
                    ob.invalidation_ts = pd.Timestamp(ts[b])
                    break
            ob.deepest_penetration_pct = float(deepest)
            if (not ob.invalidated and not ob.fully_mitigated and
                    ob.mitigation_count == 0):
                # untouched within age window -> stale but not invalidated
                ob.freshness = "stale"
                if ob.lifecycle == "fresh":
                    ob.lifecycle = "fresh"
