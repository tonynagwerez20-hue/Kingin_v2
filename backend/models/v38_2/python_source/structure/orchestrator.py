"""Market-structure orchestrator.

Combines swing, structure (BOS/CHOCH/legs/protected), OB, liquidity, EQH/EQL,
inducement, FVG, and premium/discount engines into one per-timeframe state
object, and links HTF↔LTF legs into a multi-leg hierarchy.

Provides `snapshot(bar_index)` — the *leakage-safe* structural view as of a
bar: only objects whose `confirmation_bar <= bar_index` are visible. This is
the single entry point the feature engine and dataset generator use, so
look-ahead is impossible by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import V38Config
from .swing_engine import Swing, detect_swings
from .structure_engine import StructureEngine, regime_at
from .ob_engine import OrderBlockEngine
from .liquidity_engine import LiquidityEngine
from .fvg_engine import FVGEngine
from .pd_engine import PremiumDiscountEngine
from .objects import StructuralEvent, StructuralLeg, ProtectedLevel
from .ob_objects import OrderBlock
from .liq_objects import LiquidityPool, EqualLevel, Inducement
from .fvg_objects import FairValueGap
from .pd_engine import PremiumDiscount


@dataclass
class TimeframeStructure:
    timeframe: str
    df: pd.DataFrame
    swings: List[Swing]
    events: List[StructuralEvent]
    legs: List[StructuralLeg]
    protected: List[ProtectedLevel]
    order_blocks: List[OrderBlock]
    pools: List[LiquidityPool]
    equals: List[EqualLevel]
    inducements: List[Inducement]
    fvgs: List[FairValueGap]
    pd_series: List[PremiumDiscount]
    regime_series: List[dict]

    # sorted indices for binary-search-style "latest confirmed <= bar" queries
    _sw_conf: List[int] = field(default_factory=list)
    _ev_conf: List[int] = field(default_factory=list)
    _leg_conf: List[int] = field(default_factory=list)
    _prot_conf: List[int] = field(default_factory=list)
    _ob_conf: List[int] = field(default_factory=list)
    _pool_conf: List[int] = field(default_factory=list)
    _eq_conf: List[int] = field(default_factory=list)
    _fvg_conf: List[int] = field(default_factory=list)


def build_timeframe(df: pd.DataFrame, cfg: V38Config, symbol: str,
                    timeframe: str) -> TimeframeStructure:
    swings = detect_swings(df, cfg)
    se = StructureEngine(cfg, symbol, timeframe)
    events, legs, protected, regime_series = se.build(df, swings)
    obe = OrderBlockEngine(cfg, symbol, timeframe)
    order_blocks = obe.build(df, events)
    le = LiquidityEngine(cfg, symbol, timeframe)
    pools, equals, inducements = le.build(df, swings, events, legs)
    fe = FVGEngine(cfg, symbol, timeframe)
    fvgs = fe.build(df, events)
    pe = PremiumDiscountEngine(cfg, timeframe)
    pd_series = pe.build_series(df, legs)

    ts = TimeframeStructure(
        timeframe=timeframe, df=df, swings=swings, events=events, legs=legs,
        protected=protected, order_blocks=order_blocks, pools=pools,
        equals=equals, inducements=inducements, fvgs=fvgs,
        pd_series=pd_series, regime_series=regime_series,
    )
    ts._sw_conf = [s.confirmation_bar for s in swings]
    ts._ev_conf = [e.confirmation_bar for e in events]
    ts._leg_conf = [l.confirmation_bar for l in legs]
    ts._prot_conf = [p.confirmation_bar for p in protected]
    ts._ob_conf = [o.confirmation_bar for o in order_blocks]
    ts._pool_conf = [p.confirmation_bar for p in pools]
    ts._eq_conf = [e.confirmation_bar for e in equals]
    ts._fvg_conf = [f.confirmation_bar for f in fvgs]
    return ts


def _latest_confirmed(conf_idx: List[int], items: list, bar_index: int) -> List:
    """Return items whose confirmation_bar <= bar_index (no look-ahead)."""
    if not conf_idx:
        return []
    import bisect
    end = bisect.bisect_right(conf_idx, bar_index)
    return items[:end]


def _precompute_windows(conf_idx: List[int], items: list) -> List[int]:
    """For each bar b in [0, max_bar], the count of items confirmed by b."""
    if not conf_idx:
        return []
    max_bar = max(conf_idx) if conf_idx else 0
    counts = [0] * (max_bar + 1)
    for c in conf_idx:
        if 0 <= c <= max_bar:
            counts[c] += 1
    cum = 0
    for b in range(len(counts)):
        cum += counts[b]
        counts[b] = cum
    return counts


def _window_sizes(conf_idx: List[int], n: int) -> List[int]:
    """Return per-bar window sizes [0..n-1] (cumulative confirmed count)."""
    if not conf_idx or n == 0:
        return [0] * max(1, n)
    max_bar = max(conf_idx)
    size = max(n, max_bar + 1)
    counts = [0] * size
    for c in conf_idx:
        if 0 <= c < size:
            counts[c] += 1
    cum = 0
    for b in range(size):
        cum += counts[b]
        counts[b] = cum
    # slice to n (bars beyond max_bar hold the final cumulative count)
    return counts[:n] if n <= size else counts + [counts[-1]] * (n - size)


class MarketStructure:
    """Multi-timeframe structural state with leakage-safe snapshots."""

    def __init__(self, cfg: V38Config, symbol: str = "XAUUSD"):
        self.cfg = cfg
        self.symbol = symbol
        self.tfs: Dict[str, TimeframeStructure] = {}

    def add_timeframe(self, timeframe: str, df: pd.DataFrame):
        t = build_timeframe(df, self.cfg, self.symbol, timeframe)
        # precompute per-bar confirmed-window sizes for O(1) snapshots
        n = len(df)
        t._sw_win = _window_sizes(t._sw_conf, n)
        t._ev_win = _window_sizes(t._ev_conf, n)
        t._leg_win = _window_sizes(t._leg_conf, n)
        t._prot_win = _window_sizes(t._prot_conf, n)
        t._ob_win = _window_sizes(t._ob_conf, n)
        t._pool_win = _window_sizes(t._pool_conf, n)
        t._eq_win = _window_sizes(t._eq_conf, n)
        t._fvg_win = _window_sizes(t._fvg_conf, n)
        self.tfs[timeframe] = t

    def snapshot_at_ts(self, timeframe: str, ts: pd.Timestamp) -> dict:
        """Leakage-safe snapshot as of a timestamp (correct cross-TF mapping).

        Finds the last bar in `timeframe` whose open-time <= ts and returns
        the snapshot at that bar index. This is the correct way to query an
        HTF structure from an LTF bar timestamp — avoids index mismatch and
        the leakage of looking at a future HTF bar.
        """
        t = self.tfs[timeframe]
        ts_arr = t.df["ts"].to_numpy().astype("datetime64[ns]")
        target = np.datetime64(ts.replace(tzinfo=None))
        idx = int(np.searchsorted(ts_arr, target, side="right")) - 1
        if idx < 0:
            idx = 0
        return self.snapshot(timeframe, idx)

    def snapshot(self, timeframe: str, bar_index: int) -> dict:
        """Leakage-safe view of all structure as of `bar_index` (inclusive).

        bar_index is in the timeframe's own bars; for cross-TF queries the
        caller passes the HTF bar index. To stay robust when an LTF bar index
        is passed for an HTF that has fewer bars, clamp to the last available
        HTF bar (the regime/state at that time is the most recent confirmed).
        """
        t = self.tfs[timeframe]
        n = len(t.df)
        bi = min(bar_index, n - 1)
        if bi < 0:
            bi = 0
        return {
            "timeframe": timeframe,
            "bar_index": bi,
            "regime": regime_at(t.regime_series, bi),
            "swings": t.swings[:t._sw_win[bi]] if hasattr(t, "_sw_win") else _latest_confirmed(t._sw_conf, t.swings, bi),
            "events": t.events[:t._ev_win[bi]] if hasattr(t, "_ev_win") else _latest_confirmed(t._ev_conf, t.events, bi),
            "legs": t.legs[:t._leg_win[bi]] if hasattr(t, "_leg_win") else _latest_confirmed(t._leg_conf, t.legs, bi),
            "protected": t.protected[:t._prot_win[bi]] if hasattr(t, "_prot_win") else _latest_confirmed(t._prot_conf, t.protected, bi),
            "order_blocks": t.order_blocks[:t._ob_win[bi]] if hasattr(t, "_ob_win") else _latest_confirmed(t._ob_conf, t.order_blocks, bi),
            "pools": t.pools[:t._pool_win[bi]] if hasattr(t, "_pool_win") else _latest_confirmed(t._pool_conf, t.pools, bi),
            "equals": t.equals[:t._eq_win[bi]] if hasattr(t, "_eq_win") else _latest_confirmed(t._eq_conf, t.equals, bi),
            "inducements": t.inducements[:t._ev_win[bi]] if hasattr(t, "_ev_win") else _latest_confirmed(t._ev_conf, t.inducements, bi),
            "fvgs": t.fvgs[:t._fvg_win[bi]] if hasattr(t, "_fvg_win") else _latest_confirmed(t._fvg_conf, t.fvgs, bi),
            "pd": t.pd_series[bi] if bi < len(t.pd_series) else None,
        }

    def link_multi_leg(self, htf: str, ltf: str) -> List[Tuple[str, str]]:
        """Link LTF legs to the HTF leg that contains them (parent/child).

        Returns list of (htf_leg_id, ltf_leg_id). A leg is 'contained' if its
        confirmation falls within the HTF leg's [start_bar, end_bar] window.
        """
        if htf not in self.tfs or ltf not in self.tfs:
            return []
        links: List[Tuple[str, str]] = []
        for hleg in self.tfs[htf].legs:
            for lleg in self.tfs[ltf].legs:
                if (lleg.confirmation_bar >= hleg.start_bar and
                        lleg.confirmation_bar <= hleg.end_bar):
                    links.append((hleg.leg_id, lleg.leg_id))
        return links
