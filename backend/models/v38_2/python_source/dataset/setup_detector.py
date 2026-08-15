"""Candidate setup detector — genuine SMC setups, NOT every candle.

A candidate setup is a bar where, after the (leakage-safe) snapshot, the
structural confluence for a directional trade exists:

  Bullish candidate (long):
    - LTF regime bullish OR a bullish CHOCH just confirmed,
    - an active bullish OB or bullish open FVG below/at price (discount entry),
    - premium/discount in discount or equilibrium,
    - liquidity target above (nearest pool of opposite side),
    - HTF regime not bearish (alignment >= 0).
  Bearish candidate: mirror.

The detector does not guarantee the trade will win — it only marks genuine
candidate setup states. The labeler decides the outcome. This is the unit of
observation for the dataset, so the count is bounded by real structure, not by
the number of bars.

Every candidate records the EXACT pre-entry snapshot: identity, market state,
structure, SMC, macro, signal (direction/entry/SL/TP/RR), and the feature
vector — all frozen at the bar BEFORE entry (no future info).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import V38Config, DATASET_VERSION
from ..bars import atr, session_of
from ..structure.orchestrator import MarketStructure
from ..macro.engine import MacroEngine
from ..features.engine import FeatureEngine, features_as_dict
from ..features.contract import FEATURE_NAMES


@dataclass
class CandidateSetup:
    # identity
    setup_id: str
    timestamp: pd.Timestamp
    symbol: str
    timeframe: str
    dataset_version: str
    bar_index: int
    # market state
    open: float
    high: float
    low: float
    close: float
    atr: float
    spread: float
    session: str
    # signal
    direction: str
    setup_type: str
    entry_price: float
    sl: float
    tp: float
    rr: float
    # feature vector (canonical contract)
    feature_vector: List[float]
    feature_names: List[str] = field(default_factory=lambda: list(FEATURE_NAMES))
    # label (filled by labeler)
    label: Optional[int] = None
    future_return: Optional[float] = None
    barrier_reached: Optional[str] = None  # "TP" | "SL" | "censored"
    mfe: Optional[float] = None
    mae: Optional[float] = None
    time_to_resolution: Optional[int] = None


class SetupDetector:
    def __init__(self, cfg: V38Config, ms: MarketStructure,
                 macro: Optional[MacroEngine] = None,
                 ltf: str = "H1", htf: str = "H4"):
        self.cfg = cfg
        self.ms = ms
        self.macro = macro
        self.ltf = ltf
        self.htf = htf
        self.fe = FeatureEngine(cfg, ms, macro, ltf=ltf, htf=htf)

    def detect_all(self) -> List[CandidateSetup]:
        df = self.ms.tfs[self.ltf].df
        n = len(df)
        setups: List[CandidateSetup] = []
        counter = 0
        # skip the first bars where structure/ATR cannot be confirmed
        start = max(self.cfg.swing_strength * 2 + 1,
                    self.cfg.displacement_atr_period + 1, 50)
        for b in range(start, n):
            for direction in ("bullish", "bearish"):
                snap = self.ms.snapshot(self.ltf, b)
                if not self._is_candidate(snap, direction, b, df):
                    continue
                feat = self.fe.vector(b, direction)
                counter += 1
                row = df.iloc[b]
                entry = float(row["close"])
                sl_dist, tp = self._sl_tp(snap, direction, entry, feat)
                if sl_dist <= 0:
                    continue
                sl = entry - sl_dist if direction == "bullish" else entry + sl_dist
                setups.append(CandidateSetup(
                    setup_id=f"S{counter}",
                    timestamp=pd.Timestamp(row["ts"]),
                    symbol=self.ms.symbol, timeframe=self.ltf,
                    dataset_version=DATASET_VERSION, bar_index=b,
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    atr=feat[37], spread=float(row["spread"]),
                    session=session_of(pd.Timestamp(row["ts"]), self.cfg),
                    direction=direction, setup_type=self._setup_type(snap, direction),
                    entry_price=entry, sl=sl, tp=tp,
                    rr=float(feat[55]),
                    feature_vector=[float(x) for x in feat],
                ))
        return setups

    # ----------------------------------------------------------- helpers
    def _is_candidate(self, snap, direction: str, b: int, df) -> bool:
        regime = snap["regime"]
        if self.htf in self.ms.tfs and b < len(self.fe._htf_idx_for_ltf):
            htf_snap = self.ms.snapshot(self.htf, int(self.fe._htf_idx_for_ltf[b]))
        else:
            htf_snap = None
        htf_regime = htf_snap["regime"] if htf_snap else "neutral"

        # alignment: LTF regime must not contradict direction; HTF not against
        if direction == "bullish" and regime == "bearish":
            # allow only if a bullish CHOCH just confirmed (last event)
            evs = [e for e in snap["events"][-3:] if e.event_type == "CHOCH" and e.direction == "bullish"]
            if not evs:
                return False
        if direction == "bearish" and regime == "bullish":
            evs = [e for e in snap["events"][-3:] if e.event_type == "CHOCH" and e.direction == "bearish"]
            if not evs:
                return False
        if direction == "bullish" and htf_regime == "bearish":
            return False
        if direction == "bearish" and htf_regime == "bullish":
            return False

        # require a confluence element in the trade direction
        valid_obs = [o for o in snap["order_blocks"]
                     if not o.invalidated and o.lifecycle in ("fresh", "touched", "partially_consumed")
                     and o.direction == direction]
        open_fvgs = [f for f in snap["fvgs"]
                     if f.lifecycle in ("open", "partially_filled") and f.direction == direction]
        if not valid_obs and not open_fvgs:
            return False

        # premium/discount gate
        pd_state = snap["pd"]
        if pd_state and pd_state.leg_id is not None:
            pos = pd_state.position
            if direction == "bullish" and pos > 0.6:
                return False  # buying in deep premium — skip
            if direction == "bearish" and pos < 0.4:
                return False  # selling in deep discount — skip

        # require a liquidity target on the opposite side
        price = float(df["close"].to_numpy()[b])
        pools = [p for p in snap["pools"] if not p.invalidated]
        if direction == "bullish":
            target = [p for p in pools if p.price > price]
        else:
            target = [p for p in pools if p.price < price]
        if not target:
            return False

        # quality gate
        if self._setup_quality(snap, direction) < self.cfg.min_setup_quality:
            return False
        return True

    @staticmethod
    def _setup_type(snap, direction: str) -> str:
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        last = evs[-1] if evs else None
        if last and last.event_type == "CHOCH" and last.direction == direction:
            return "CHOCH_reversal"
        if last and last.event_type == "BOS" and last.direction == direction:
            return "BOS_continuation"
        return "confluence"

    @staticmethod
    def _setup_quality(snap, direction: str) -> float:
        score = 0.0
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        if evs:
            score += 0.4 * evs[-1].quality
        valid_obs = [o for o in snap["order_blocks"]
                     if not o.invalidated and o.direction == direction]
        if valid_obs:
            score += 0.3
        open_fvgs = [f for f in snap["fvgs"]
                     if f.lifecycle in ("open", "partially_filled") and f.direction == direction]
        if open_fvgs:
            score += 0.2
        swept = [p for p in snap["pools"] if p.swept]
        if swept:
            score += 0.1
        return min(1.0, score)

    def _sl_tp(self, snap, direction, price, feat) -> tuple:
        prots_h = [p for p in snap["protected"] if p.kind == "high" and p.status == "active"]
        prots_l = [p for p in snap["protected"] if p.kind == "low" and p.status == "active"]
        if direction == "bullish":
            ref = min([p.price for p in prots_l], default=price - feat[37])
            sl_dist = max(feat[37] * 0.5, price - ref)
            tp = price + sl_dist * self.cfg.label_tp_r
        else:
            ref = max([p.price for p in prots_h], default=price + feat[37])
            sl_dist = max(feat[37] * 0.5, ref - price)
            tp = price - sl_dist * self.cfg.label_tp_r
        return sl_dist, tp
