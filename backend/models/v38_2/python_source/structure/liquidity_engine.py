"""Liquidity engine: pool mapping, EQH/EQL (ATR-tolerance), inducement.

A liquidity pool is a price level created from a swing (high/low), clustered
levels, equal highs/lows, or obvious range boundaries (PDH/PWH/session H/L).
Each pool tracks touches, strength, sweep status, and post-sweep reaction.

EQH/EQL uses an ATR-normalized tolerance (NOT a fixed price tick). Two swings
of the same polarity whose prices differ by <= eqh_eql_atr_tol * ATR are equal.

Inducement: a minor swing that lies between price and a larger structural
liquidity objective. It is a structural concept: a short-term high/low that
would likely be swept to reach the real objective. Tracked with parent leg +
intended liquidity + sweep status.

All objects carry confirmation_bar (leakage boundary).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import V38Config
from ..bars import atr
from .swing_engine import Swing
from .liq_objects import LiquidityPool, EqualLevel, Inducement
from .objects import StructuralLeg, StructuralEvent


class LiquidityEngine:
    def __init__(self, cfg: V38Config, symbol: str = "XAUUSD", timeframe: str = "H1"):
        self.cfg = cfg
        self.symbol = symbol
        self.timeframe = timeframe

    def build(self, df: pd.DataFrame, swings: List[Swing],
              events: List[StructuralEvent], legs: List[StructuralLeg]
              ) -> Tuple[List[LiquidityPool], List[EqualLevel], List[Inducement]]:
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        ts = df["ts"].to_numpy()
        atr_arr = atr(df, self.cfg.displacement_atr_period)
        prev_close = np.empty(len(df))
        prev_close[0] = closes[0]
        prev_close[1:] = closes[:-1]
        tr = np.maximum.reduce([
            highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close),
        ])
        atr_safe = np.where(np.isnan(atr_arr), tr, atr_arr)

        pools = self._build_pools(swings, ts, atr_safe, highs, lows, closes)
        equals = self._build_equal_levels(swings, atr_safe)
        inducements = self._build_inducements(swings, legs, ts, atr_safe)
        return pools, equals, inducements

    # ------------------------------------------------------------------ pools
    def _build_pools(self, swings: List[Swing], ts, atr_safe, highs, lows, closes
                     ) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        # cluster same-polarity swings within liquidity_cluster_atr into one pool
        cluster_atr = self.cfg.liquidity_cluster_atr
        by_kind: dict = {"high": [], "low": []}
        for s in swings:
            by_kind[s.kind].append(s)
        counter = 0
        for kind, lst in by_kind.items():
            lst = sorted(lst, key=lambda s: s.confirmation_bar)
            i = 0
            while i < len(lst):
                base = lst[i]
                members = [base]
                j = i + 1
                while j < len(lst):
                    a = atr_safe[base.confirmation_bar] if base.confirmation_bar < len(atr_safe) else 1.0
                    a = a if a > 0 else 1.0
                    if abs(lst[j].price - base.price) <= cluster_atr * a:
                        members.append(lst[j])
                        j += 1
                    else:
                        break
                price = float(np.mean([m.price for m in members]))
                counter += 1
                pool = LiquidityPool(
                    pool_id=f"LP{counter}_{self.timeframe}",
                    type=kind, price=price,
                    creation_ts=base.ts, creation_bar=base.bar_index,
                    source_swings=[m.swing_id for m in members],
                    touches=len(members),
                    strength=float(min(1.0, len(members) / 4.0)),
                    confirmation_bar=members[-1].confirmation_bar,
                    confirmation_ts=members[-1].confirmation_ts,
                )
                pools.append(pool)
                i = j
        # Sweep detection: a later bar takes out the pool then closes back.
        self._mark_sweeps(pools, highs, lows, closes, ts, atr_safe)
        return pools

    def _mark_sweeps(self, pools, highs, lows, closes, ts, atr_safe) -> None:
        n = len(closes)
        for p in pools:
            for b in range(p.confirmation_bar + 1, n):
                if p.type == "high" and highs[b] > p.price and closes[b] < p.price:
                    p.sweep_bar = b
                    p.sweep_ts = pd.Timestamp(ts[b])
                    p.swept = True
                    a = atr_safe[b] if b < len(atr_safe) else 1.0
                    a = a if a > 0 else 1.0
                    depth = (highs[b] - p.price) / a
                    p.sweep_depth_atr = float(depth)
                    # post-sweep reaction: max excursion opposite within 10 bars
                    end = min(n, b + 11)
                    if p.type == "high":
                        mfe = (p.price - min(lows[b:end])) if end > b else 0.0
                    else:
                        mfe = (max(highs[b:end]) - p.price) if end > b else 0.0
                    p.post_sweep_reaction_atr = float(mfe / a) if a > 0 else 0.0
                    break
                if p.type == "low" and lows[b] < p.price and closes[b] > p.price:
                    p.sweep_bar = b
                    p.sweep_ts = pd.Timestamp(ts[b])
                    p.swept = True
                    a = atr_safe[b] if b < len(atr_safe) else 1.0
                    a = a if a > 0 else 1.0
                    depth = (p.price - lows[b]) / a
                    p.sweep_depth_atr = float(depth)
                    end = min(n, b + 11)
                    if p.type == "high":
                        mfe = (p.price - min(lows[b:end])) if end > b else 0.0
                    else:
                        mfe = (max(highs[b:end]) - p.price) if end > b else 0.0
                    p.post_sweep_reaction_atr = float(mfe / a) if a > 0 else 0.0
                    break

    # ------------------------------------------------------------ EQH / EQL
    def _build_equal_levels(self, swings: List[Swing], atr_safe) -> List[EqualLevel]:
        equals: List[EqualLevel] = []
        tol_mult = self.cfg.eqh_eql_atr_tol
        by_kind: dict = {"high": [], "low": []}
        for s in swings:
            by_kind[s.kind].append(s)
        counter = 0
        for kind, lst in by_kind.items():
            lst = sorted(lst, key=lambda s: s.confirmation_bar)
            used = [False] * len(lst)
            for i in range(len(lst)):
                if used[i]:
                    continue
                a = atr_safe[lst[i].confirmation_bar] if lst[i].confirmation_bar < len(atr_safe) else 1.0
                a = a if a > 0 else 1.0
                tol = tol_mult * a
                group = [lst[i]]
                used[i] = True
                for j in range(i + 1, len(lst)):
                    if used[j]:
                        continue
                    if abs(lst[j].price - lst[i].price) <= tol:
                        group.append(lst[j])
                        used[j] = True
                if len(group) >= 2:
                    counter += 1
                    equals.append(EqualLevel(
                        equal_id=f"EQ{counter}_{self.timeframe}",
                        type=kind,
                        first_bar=group[0].bar_index, first_ts=group[0].ts,
                        first_price=group[0].price,
                        second_bar=group[-1].bar_index, second_ts=group[-1].ts,
                        second_price=group[-1].price,
                        price_diff=float(abs(group[-1].price - group[0].price)),
                        normalized_diff=float(abs(group[-1].price - group[0].price) / a),
                        num_equal=len(group),
                        confirmation_bar=group[-1].confirmation_bar,
                        confirmation_ts=group[-1].confirmation_ts,
                    ))
        return equals

    # ----------------------------------------------------------- inducement
    def _build_inducements(self, swings: List[Swing], legs: List[StructuralLeg],
                           ts, atr_safe) -> List[Inducement]:
        """An inducement is a minor (internal) swing that sits between current
        price and a larger structural objective (leg end). We pair each leg with
        the internal swings that occurred during the leg and lie in the path of
        the objective."""
        out: List[Inducement] = []
        internal = [s for s in swings if not s.external]
        counter = 0
        for leg in legs:
            # internal swings whose confirmation falls inside the leg window
            in_leg = [s for s in internal
                      if leg.start_bar <= s.confirmation_bar <= leg.end_bar]
            objective_price = leg.end_price
            for s in in_leg:
                counter += 1
                out.append(Inducement(
                    inducement_id=f"IND{counter}_{self.timeframe}",
                    parent_leg_id=leg.leg_id,
                    inducement_swing_id=s.swing_id,
                    inducement_price=s.price,
                    intended_liquidity=objective_price,
                    creation_ts=s.ts, creation_bar=s.bar_index,
                    confirmation_bar=s.confirmation_bar,
                    confirmation_ts=s.confirmation_ts,
                ))
        return out
