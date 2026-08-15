"""BOS / CHOCH / regime / multi-leg structure engine.

This is the heart of the V38 structure engine. It scans the confirmed swing
sequence produced by the swing engine and emits structural events:

  BOS   — break of the most recent *external* swing in the direction of the
          prevailing regime (continuation). Requires the broken swing to be a
          legitimate structural (external) swing, not an arbitrary candle.
  CHOCH — break of the protected level *against* the prevailing regime, with
          displacement >= choch_min_atr_mult (a character change, not just any
          counter-trend poke).

Both events record detection and confirmation bars. An event is only usable
after its `confirmation_bar` (the bar that printed the break close/wick), so
features cannot read structure that was not yet available.

A structural leg is the run between two consecutive external swings of
opposite polarity whose direction matches the prevailing regime. Legs carry
high/low/equilibrium used by the premium/discount engine.

Multi-leg: each TF builds its own legs; the orchestrator links HTF legs to LTF
legs via `parent_leg_id` (see orchestrator). Here we expose leg building per TF.

The regime is tracked as a running state that flips on CHOCH and continues on
BOS. It starts neutral until the first external-swing break.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import V38Config
from ..bars import atr
from .swing_engine import Swing
from .objects import StructuralEvent, StructuralLeg, ProtectedLevel, REGIMES


class StructureEngine:
    def __init__(self, cfg: V38Config, symbol: str = "XAUUSD", timeframe: str = "H1"):
        self.cfg = cfg
        self.symbol = symbol
        self.timeframe = timeframe

    def build(self, df: pd.DataFrame, swings: List[Swing]) -> Tuple[
            List[StructuralEvent], List[StructuralLeg], List[ProtectedLevel], List[dict]]:
        """Return (events, legs, protected_levels, regime_series).

        regime_series: list of {bar_index, ts, regime} for every bar — the
        regime *as known at that bar* (no look-ahead: regime at bar i uses only
        events with confirmation_bar <= i).
        """
        closes = df["close"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        ts = df["ts"].to_numpy()
        atr_arr = atr(df, self.cfg.displacement_atr_period)
        prev_close = np.empty(len(df))
        prev_close[0] = closes[0]
        prev_close[1:] = closes[:-1]
        tr = np.maximum.reduce([
            highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close),
        ])
        tr = np.where(np.isnan(atr_arr), tr, atr_arr)

        # External swings only, chronological by confirmation.
        ext = [s for s in swings if s.external]
        ext_sorted = sorted(ext, key=lambda s: s.confirmation_bar)

        events: List[StructuralEvent] = []
        legs: List[StructuralLeg] = []
        protected: List[ProtectedLevel] = []

        # Running state
        regime = "neutral"
        last_protected_high: Optional[ProtectedLevel] = None
        last_protected_low: Optional[ProtectedLevel] = None
        last_external_high: Optional[Swing] = None
        last_external_low: Optional[Swing] = None
        leg_start_swing: Optional[Swing] = None
        event_counter = 0
        leg_counter = 0
        prot_counter = 0

        # We process bars in order; when an external swing becomes confirmed,
        # update protected levels, then check for breaks against them on each
        # subsequent bar. To keep it causal, iterate over bars and lazily adopt
        # newly-confirmed swings.
        ext_by_conf = list(ext_sorted)
        ext_idx = 0  # pointer into ext_by_conf

        # Per-bar regime log
        regime_series: List[dict] = []
        # active break-check state per bar
        pending_break = None

        n = len(df)
        for b in range(n):
            # Adopt swings confirmed at this bar.
            while ext_idx < len(ext_by_conf) and ext_by_conf[ext_idx].confirmation_bar <= b:
                s = ext_by_conf[ext_idx]
                if s.kind == "high":
                    last_external_high = s
                    # A newly confirmed external high becomes a protected high
                    # candidate only if it is the highest relevant high; the
                    # protecting event is the most recent bullish event if any.
                    prot_counter += 1
                    pl = ProtectedLevel(
                        protected_id=f"PH{prot_counter}_{self.timeframe}",
                        kind="high", price=s.price, swing_id=s.swing_id,
                        protecting_event_id=(events[-1].event_id if events else ""),
                        ts=s.confirmation_ts, bar_index=s.confirmation_bar,
                        confirmation_bar=s.confirmation_bar,
                        confirmation_ts=s.confirmation_ts,
                    )
                    protected.append(pl)
                    if last_protected_high and last_protected_high.status == "active":
                        last_protected_high.status = "superseded"
                    last_protected_high = pl
                else:
                    last_external_low = s
                    prot_counter += 1
                    pl = ProtectedLevel(
                        protected_id=f"PL{prot_counter}_{self.timeframe}",
                        kind="low", price=s.price, swing_id=s.swing_id,
                        protecting_event_id=(events[-1].event_id if events else ""),
                        ts=s.confirmation_ts, bar_index=s.confirmation_bar,
                        confirmation_bar=s.confirmation_bar,
                        confirmation_ts=s.confirmation_ts,
                    )
                    protected.append(pl)
                    if last_protected_low and last_protected_low.status == "active":
                        last_protected_low.status = "superseded"
                    last_protected_low = pl
                ext_idx += 1

            # Check for breaks of active protected levels on this bar.
            bar_atr = float(tr[b]) if b < len(tr) else 1.0
            bar_atr = bar_atr if bar_atr > 0 else 1.0
            close = closes[b]
            high = highs[b]
            low = lows[b]

            # Bullish break: price takes out an active protected high.
            if last_protected_high and last_protected_high.status in ("active", "superseded"):
                broken_price = last_protected_high.price
                broke = (close > broken_price) if self.cfg.bos_close_required else (high > broken_price)
                if broke:
                    disp = close - last_protected_high.price
                    disp_atr = disp / bar_atr
                    is_choch = (regime in ("bearish", "neutral") and
                                disp_atr >= self.cfg.choch_min_atr_mult)
                    is_bos = (regime == "bullish" and
                              disp_atr >= self.cfg.bos_min_atr_mult)
                    if is_choch or is_bos:
                        event_counter += 1
                        etype = "CHOCH" if is_choch else "BOS"
                        ev = StructuralEvent(
                            event_id=f"EV{event_counter}_{self.timeframe}",
                            symbol=self.symbol, timeframe=self.timeframe,
                            ts=pd.Timestamp(ts[b]), bar_index=b,
                            event_type=etype, direction="bullish",
                            originating_swing_id=last_protected_high.swing_id,
                            broken_level=broken_price, break_price=high,
                            confirmation_price=close, displacement=disp,
                            displacement_atr=disp_atr,
                            protected_level_id=last_protected_high.protected_id,
                            quality=min(1.0, disp_atr / (self.cfg.choch_min_atr_mult * 3)),
                            invalidation_level=last_protected_high.price - bar_atr,
                            confirmation_bar=b, confirmation_ts=pd.Timestamp(ts[b]),
                        )
                        events.append(ev)
                        last_protected_high.status = "broken"
                        last_protected_high.break_ts = pd.Timestamp(ts[b])
                        # new protected high replaces broken one (set on next high confirm)
                        if is_choch:
                            regime = "bullish"
                            leg_start_swing = last_external_high

            # Bearish break: price takes out an active protected low.
            if last_protected_low and last_protected_low.status in ("active", "superseded"):
                broken_price = last_protected_low.price
                broke = (close < broken_price) if self.cfg.bos_close_required else (low < broken_price)
                if broke:
                    disp = last_protected_low.price - close
                    disp_atr = disp / bar_atr
                    is_choch = (regime in ("bullish", "neutral") and
                                disp_atr >= self.cfg.choch_min_atr_mult)
                    is_bos = (regime == "bearish" and
                              disp_atr >= self.cfg.bos_min_atr_mult)
                    if is_choch or is_bos:
                        event_counter += 1
                        etype = "CHOCH" if is_choch else "BOS"
                        ev = StructuralEvent(
                            event_id=f"EV{event_counter}_{self.timeframe}",
                            symbol=self.symbol, timeframe=self.timeframe,
                            ts=pd.Timestamp(ts[b]), bar_index=b,
                            event_type=etype, direction="bearish",
                            originating_swing_id=last_protected_low.swing_id,
                            broken_level=broken_price, break_price=low,
                            confirmation_price=close, displacement=disp,
                            displacement_atr=disp_atr,
                            protected_level_id=last_protected_low.protected_id,
                            quality=min(1.0, disp_atr / (self.cfg.choch_min_atr_mult * 3)),
                            invalidation_level=last_protected_low.price + bar_atr,
                            confirmation_bar=b, confirmation_ts=pd.Timestamp(ts[b]),
                        )
                        events.append(ev)
                        last_protected_low.status = "broken"
                        last_protected_low.break_ts = pd.Timestamp(ts[b])
                        if is_choch:
                            regime = "bearish"
                            leg_start_swing = last_external_low

            regime_series.append({"bar_index": b, "ts": pd.Timestamp(ts[b]),
                                   "regime": regime})

        # Build structural legs from external swings of opposite polarity
        # that bracket a directional move. A leg runs from a confirmed low to
        # the next confirmed high (bullish) or high to low (bearish).
        legs = self._build_legs(ext_sorted, ts, timeframe=self.timeframe)
        return events, legs, protected, regime_series

    def _build_legs(self, ext_swings: List[Swing], ts, timeframe: str) -> List[StructuralLeg]:
        legs: List[StructuralLeg] = []
        if len(ext_swings) < 2:
            return legs
        # alternate high/low pairs
        for i in range(1, len(ext_swings)):
            prev, cur = ext_swings[i - 1], ext_swings[i]
            if prev.kind == cur.kind:
                continue
            if prev.kind == "low" and cur.kind == "high":
                direction = "bullish"
            elif prev.kind == "high" and cur.kind == "low":
                direction = "bearish"
            else:
                continue
            hi = max(prev.price, cur.price)
            lo = min(prev.price, cur.price)
            legs.append(StructuralLeg(
                leg_id=f"LG{i}_{timeframe}",
                timeframe=timeframe, direction=direction,
                start_swing_id=prev.swing_id, end_swing_id=cur.swing_id,
                start_ts=prev.confirmation_ts, end_ts=cur.confirmation_ts,
                start_bar=prev.confirmation_bar, end_bar=cur.confirmation_bar,
                start_price=prev.price, end_price=cur.price,
                high=hi, low=lo, equilibrium=(hi + lo) / 2.0,
                confirmation_bar=cur.confirmation_bar,
                confirmation_ts=cur.confirmation_ts,
            ))
        return legs


def regime_at(regime_series: List[dict], bar_index: int) -> str:
    """Last-known regime as of bar_index (no look-ahead)."""
    if not regime_series or bar_index < 0:
        return "neutral"
    if bar_index >= len(regime_series):
        bar_index = len(regime_series) - 1
    return regime_series[bar_index]["regime"]
