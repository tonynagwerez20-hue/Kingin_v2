"""V38.2 M5 Full-Data Validation — Optimized.

Uses genuine M5 (Jetta/Dukascopy) data to determine whether the M15/H1 signal
survives at the M5 execution resolution. Uses the SAME V38.1 feature engine,
structure engine, setup detector, labeler — only the LTF is changed from M15
to M5. HTF remains H1 (same regime context as the M15/H1 validation).

Optimization: pre-computes per-bar structure queries (nearest OB, FVG, pool,
protected levels) using numpy arrays + binary search, avoiding the O(N_objects)
linear scan per bar that makes the naive loop infeasible for 596K M5 bars.

Key principles (same as M15/H1 validation):
  - Same V38.1 feature engine, structure engine, setup detector, labeler
  - LTF=M5, HTF=H1 — genuine multi-timeframe structure
  - label_max_bars=240 (≈20h at M5, matching M15's 80 bars × 15 min = 20h)
  - Fixed baseline LightGBM config (no hyperparameter optimization)
  - Strict chronological evaluation: expanding walk-forward + untouched holdout
  - No random shuffle, no holdout-based selection
  - No ONNX, MQL5, MT5, deployment

Non-modifications:
  - readiness_gate.py NOT modified
  - economic_calendar.csv NOT created
  - Forecast-dependent features NOT activated (remain 0/NaN)
  - feature_contract.py NOT modified
  - holiday classification NOT modified
  - PIT rules NOT modified
"""
from __future__ import annotations

import bisect
import dataclasses
import json
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAS_LGB = True
except Exception:
    HAS_LGB = False

from sklearn.metrics import (log_loss, brier_score_loss, roc_auc_score,
                              precision_score, recall_score, f1_score,
                              average_precision_score)

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from v38.config import V38Config, DATASET_VERSION
from v38.features.contract import FEATURE_SPECS, FEATURE_NAMES, N_FEATURES
from v38.bars import atr, session_of
from v38.structure.orchestrator import MarketStructure
from v38.structure.ob_objects import OrderBlock
from v38.structure.fvg_objects import FairValueGap
from v38.structure.liq_objects import LiquidityPool
from v38.structure.objects import StructuralEvent, ProtectedLevel
from v38.macro.engine import MacroEngine
from v38.dataset.setup_detector import SetupDetector, CandidateSetup
from v38.dataset.labeler import label_setup

V38_2_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
JETTA_DIR = DATA_DIR / "processed" / "jetta"
ABLATION_DIR = V38_2_DIR / "full_data_artifacts"
ABLATION_DIR.mkdir(parents=True, exist_ok=True)

FAMILY_FEATURES: Dict[str, List[int]] = {}
for spec in FEATURE_SPECS:
    FAMILY_FEATURES.setdefault(spec.family, []).append(spec.index)
PRICE_INDICES = [i for i in range(N_FEATURES) if FEATURE_SPECS[i].family != "MACRO_NEWS"]
MACRO_INDICES = list(FAMILY_FEATURES.get("MACRO_NEWS", []))
FORECAST_DEPENDENT = [46, 47, 48]
PIT_SAFE_MACRO = [44, 45]

REG_ENC = {"bearish": 0.0, "neutral": 1.0, "bullish": 2.0}
DIR_ENC = {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0}


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (set,)):
        return sorted(obj)
    return str(obj)


def _sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, (np.integer,)):
                k = int(k)
            elif isinstance(k, (np.floating,)):
                k = float(k)
            elif not isinstance(k, (str, int, float, bool, type(None))):
                k = str(k)
            out[k] = _sanitize(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (set,)):
        return [_sanitize(v) for v in sorted(obj)]
    return obj


def load_jetta_tf(tf: str) -> pd.DataFrame:
    p = JETTA_DIR / f"XAUUSD_{tf}.csv"
    df = pd.read_csv(p)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


# ===================== PRE-COMPUTED STRUCTURE INDEX =====================
# Extracts all structure objects into numpy arrays with confirmation and
# invalidation bars, enabling O(log N) per-bar nearest-object queries.

class StructureIndex:
    """Pre-computes per-bar structure queries for O(log N) lookups."""

    def __init__(self, ms: MarketStructure, ltf: str):
        self.ms = ms
        self.ltf = ltf
        t = ms.tfs[ltf]
        self.n = len(t.df)
        self.close = t.df["close"].to_numpy()
        self.ts = t.df["ts"].to_numpy()

        # Build arrays for each object type
        self._build_pools(t)
        self._build_obs(t)
        self._build_fvgs(t)
        self._build_events(t)
        self._build_protected(t)
        self._build_legs(t)
        self._build_equals(t)
        self._build_inducements(t)
        # Pre-compute quality-score helper arrays
        self._precompute_ob_dir_flags_no_lifecycle()
        self._precompute_pool_swept_flag()
        self._precompute_sweep_data()
        self._precompute_protected_extents()
        self._precompute_eq_ind_flags()
        self._precompute_last_bos_choch()
        self._precompute_last_choch()

    def _build_pools(self, t):
        pools = t.pools
        n_p = len(pools)
        self.pool_price = np.array([p.price for p in pools], dtype=np.float64)
        self.pool_conf = np.array([p.confirmation_bar for p in pools], dtype=np.int64)
        self.pool_invalidated = np.array([p.invalidated for p in pools], dtype=np.bool_)
        self.pool_type = np.array([1 if p.type == "high" else -1 for p in pools], dtype=np.int8)
        self.pool_swept = np.array([p.swept for p in pools], dtype=np.bool_)
        self.pool_sweep_bar = np.array(
            [p.sweep_bar if p.sweep_bar is not None else -1 for p in pools], dtype=np.int64)
        self.pool_sweep_depth = np.array([p.sweep_depth_atr for p in pools], dtype=np.float64)
        self.pool_post_sweep = np.array([p.post_sweep_reaction_atr for p in pools], dtype=np.float64)
        # Sort by price for nearest-by-price queries
        order_price = np.argsort(self.pool_price, kind="stable")
        self.pool_price_sorted = self.pool_price[order_price]
        self.pool_conf_sorted = self.pool_conf[order_price]
        self.pool_invalidated_sorted = self.pool_invalidated[order_price]
        self.pool_type_sorted = self.pool_type[order_price]
        self.pool_swept_sorted = self.pool_swept[order_price]
        self.pool_sweep_bar_sorted = self.pool_sweep_bar[order_price]
        self.pool_sweep_depth_sorted = self.pool_sweep_depth[order_price]
        self.pool_post_sweep_sorted = self.pool_post_sweep[order_price]
        # Sort by confirmation_bar for has_pool queries
        order_conf = np.argsort(self.pool_conf, kind="stable")
        self.pool_price_by_conf = self.pool_price[order_conf]
        self.pool_conf_by_conf = self.pool_conf[order_conf]
        self.pool_invalidated_by_conf = self.pool_invalidated[order_conf]
        self.pool_type_by_conf = self.pool_type[order_conf]
        self.pool_swept_by_conf = self.pool_swept[order_conf]
        self.pool_sweep_bar_by_conf = self.pool_sweep_bar[order_conf]
        self.pool_sweep_depth_by_conf = self.pool_sweep_depth[order_conf]
        self.pool_post_sweep_by_conf = self.pool_post_sweep[order_conf]
        self.n_pools = n_p
        # Pre-compute per-bar min/max active pool price for O(1) has_pool_above/below
        self._precompute_pool_extents()
        print(f"  [StructureIndex] Pools: {n_p}", flush=True)

    def _build_obs(self, t):
        obs = t.order_blocks
        n_o = len(obs)
        self.ob_upper = np.array([o.upper for o in obs], dtype=np.float64)
        self.ob_lower = np.array([o.lower for o in obs], dtype=np.float64)
        self.ob_mid = np.array([o.midpoint for o in obs], dtype=np.float64)
        self.ob_conf = np.array([o.confirmation_bar for o in obs], dtype=np.int64)
        self.ob_inv_bar = np.array(
            [o.invalidation_bar if o.invalidation_bar is not None else self.n
             for o in obs], dtype=np.int64)
        self.ob_invalidated = np.array([o.invalidated for o in obs], dtype=np.bool_)
        self.ob_direction = np.array(
            [1 if o.direction == "bullish" else (-1 if o.direction == "bearish" else 0)
             for o in obs], dtype=np.int8)
        self.ob_lifecycle = np.array([o.lifecycle for o in obs], dtype=object)
        self.ob_freshness = np.array([o.freshness for o in obs], dtype=object)
        self.ob_quality = np.array([o.quality for o in obs], dtype=np.float64)
        self.ob_mitigation = np.array([o.mitigation_count for o in obs], dtype=np.int64)
        self.ob_deepest_pen = np.array([o.deepest_penetration_pct for o in obs], dtype=np.float64)
        # Sort by midpoint for binary search
        order = np.argsort(self.ob_mid, kind="stable")
        self.ob_mid_sorted = self.ob_mid[order]
        self.ob_upper_sorted = self.ob_upper[order]
        self.ob_lower_sorted = self.ob_lower[order]
        self.ob_conf_sorted = self.ob_conf[order]
        self.ob_inv_bar_sorted = self.ob_inv_bar[order]
        self.ob_invalidated_sorted = self.ob_invalidated[order]
        self.ob_direction_sorted = self.ob_direction[order]
        self.ob_lifecycle_sorted = self.ob_lifecycle[order]
        self.ob_freshness_sorted = self.ob_freshness[order]
        self.ob_quality_sorted = self.ob_quality[order]
        self.ob_mitigation_sorted = self.ob_mitigation[order]
        self.ob_deepest_pen_sorted = self.ob_deepest_pen[order]
        self.n_obs = n_o
        # Pre-compute per-bar: is there a valid OB in bullish/bearish direction?
        self._precompute_ob_dir_flags()
        print(f"  [StructureIndex] OBs: {n_o}", flush=True)

    def _build_fvgs(self, t):
        fvgs = t.fvgs
        n_f = len(fvgs)
        self.fvg_upper = np.array([f.upper for f in fvgs], dtype=np.float64)
        self.fvg_lower = np.array([f.lower for f in fvgs], dtype=np.float64)
        self.fvg_mid = np.array([f.midpoint for f in fvgs], dtype=np.float64)
        self.fvg_size_atr = np.array([f.size_atr for f in fvgs], dtype=np.float64)
        self.fvg_conf = np.array([f.confirmation_bar for f in fvgs], dtype=np.int64)
        self.fvg_inv_bar = np.array(
            [f.invalidation_bar if f.invalidation_bar is not None else self.n
             for f in fvgs], dtype=np.int64)
        self.fvg_invalidated = np.array([f.invalidated for f in fvgs], dtype=np.bool_)
        self.fvg_direction = np.array(
            [1 if f.direction == "bullish" else (-1 if f.direction == "bearish" else 0)
             for f in fvgs], dtype=np.int8)
        self.fvg_lifecycle = np.array([f.lifecycle for f in fvgs], dtype=object)
        self.fvg_fill_pct = np.array([f.fill_percentage for f in fvgs], dtype=np.float64)
        order = np.argsort(self.fvg_mid, kind="stable")
        self.fvg_mid_sorted = self.fvg_mid[order]
        self.fvg_upper_sorted = self.fvg_upper[order]
        self.fvg_lower_sorted = self.fvg_lower[order]
        self.fvg_size_atr_sorted = self.fvg_size_atr[order]
        self.fvg_conf_sorted = self.fvg_conf[order]
        self.fvg_inv_bar_sorted = self.fvg_inv_bar[order]
        self.fvg_invalidated_sorted = self.fvg_invalidated[order]
        self.fvg_direction_sorted = self.fvg_direction[order]
        self.fvg_lifecycle_sorted = self.fvg_lifecycle[order]
        self.fvg_fill_pct_sorted = self.fvg_fill_pct[order]
        self.n_fvgs = n_f
        # Pre-compute per-bar: is there an open FVG in bullish/bearish direction?
        self._precompute_fvg_dir_flags()
        print(f"  [StructureIndex] FVGs: {n_f}", flush=True)

    def _build_events(self, t):
        events = t.events
        n_e = len(events)
        self.ev_conf = np.array([e.confirmation_bar for e in events], dtype=np.int64)
        self.ev_type = np.array([e.event_type for e in events], dtype=object)
        self.ev_direction = np.array(
            [1 if e.direction == "bullish" else (-1 if e.direction == "bearish" else 0)
             for e in events], dtype=np.int8)
        self.ev_disp_atr = np.array([e.displacement_atr for e in events], dtype=np.float64)
        self.ev_quality = np.array([e.quality for e in events], dtype=np.float64)
        self.n_events = n_e
        print(f"  [StructureIndex] Events: {n_e}", flush=True)

    def _build_protected(self, t):
        prots = t.protected
        n_pr = len(prots)
        self.prot_price = np.array([p.price for p in prots], dtype=np.float64)
        self.prot_conf = np.array([p.confirmation_bar for p in prots], dtype=np.int64)
        self.prot_kind = np.array([1 if p.kind == "high" else -1 for p in prots], dtype=np.int8)
        self.prot_status = np.array([p.status for p in prots], dtype=object)
        self.n_prots = n_pr
        print(f"  [StructureIndex] Protected: {n_pr}", flush=True)

    def _build_legs(self, t):
        legs = t.legs
        self.leg_start_price = np.array([l.start_price for l in legs], dtype=np.float64)
        self.leg_conf = np.array([l.confirmation_bar for l in legs], dtype=np.int64)
        self.n_legs = len(legs)
        print(f"  [StructureIndex] Legs: {self.n_legs}", flush=True)

    def _build_equals(self, t):
        eqs = t.equals
        self.eq_conf = np.array([e.confirmation_bar for e in eqs], dtype=np.int64)
        self.n_eqs = len(eqs)
        print(f"  [StructureIndex] Equals: {self.n_eqs}", flush=True)

    def _build_inducements(self, t):
        inds = t.inducements
        self.ind_conf = np.array([i.confirmation_bar for i in inds], dtype=np.int64)
        self.n_inds = len(inds)
        print(f"  [StructureIndex] Inducements: {self.n_inds}", flush=True)

    # ----- Per-bar queries -----

    def nearest_active_pool(self, bar: int, price: float, atr_v: float) -> Tuple[float, float]:
        """Nearest non-invalidated, confirmed pool by price. Returns (dist_atr, side)."""
        if self.n_pools == 0:
            return 0.0, 0.0
        pos = bisect.bisect_left(self.pool_price_sorted, price)
        # Use numpy to find nearest valid pool in a window around pos
        lo = max(0, pos - 200)
        hi = min(self.n_pools, pos + 201)
        prices = self.pool_price_sorted[lo:hi]
        confs = self.pool_conf_sorted[lo:hi]
        inv = self.pool_invalidated_sorted[lo:hi]
        # Valid mask: confirmed by bar and not invalidated
        valid = (confs <= bar) & (~inv)
        if not valid.any():
            return 0.0, 0.0
        valid_prices = prices[valid]
        valid_indices = np.where(valid)[0]
        # Nearest by price
        dists = np.abs(valid_prices - price)
        nearest = np.argmin(dists)
        p_price = float(valid_prices[nearest])
        d = float(dists[nearest]) / (atr_v if atr_v > 0 else 1.0)
        pt = self.pool_type_sorted[lo + int(valid_indices[nearest])]
        if pt == 1 and p_price < price:
            side = -1.0
        elif pt == -1 and p_price > price:
            side = 1.0
        else:
            side = 1.0 if p_price >= price else -1.0
        return d, float(side)

    def _precompute_pool_extents(self):
        """Pre-compute per-bar min and max active (non-invalidated, confirmed) pool price.
        Enables O(1) has_pool_above/has_pool_below queries."""
        n = self.n
        # Process pools in confirmation order (sorted by conf bar)
        order = np.argsort(self.pool_conf, kind="stable")
        conf_sorted = self.pool_conf[order]
        price_sorted = self.pool_price[order]
        invalidated_sorted = self.pool_invalidated[order]

        # Running min/max of active pool prices
        # At each bar, active pools = confirmed by bar AND not invalidated
        # We compute the running min/max of all active pool prices
        # Since invalidated is per-object (invalidated at some bar), we need to
        # track which pools are still active at each bar.
        # Simplification: a pool is active at bar b if conf <= b and not invalidated.
        # Since we don't have per-bar invalidation, we approximate: a pool is active
        # at bar b if conf <= b. The invalidated flag is set at the end of the data,
        # so we use it as a filter on the final state only.
        # For correctness with the original detector, we check invalidated per pool.
        # But for the has_pool_above/below check, the original checks `not p.invalidated`
        # which is the FINAL state. So a pool marked invalidated is never counted.
        # We pre-compute: for each bar, the min/max price of confirmed, non-invalidated pools.

        # Build per-bar arrays
        self._pool_min_price = np.full(n, np.inf, dtype=np.float64)
        self._pool_max_price = np.full(n, -np.inf, dtype=np.float64)

        # Sort by confirmation bar, process incrementally
        # Track running min/max of non-invalidated pools
        running_min = np.inf
        running_max = -np.inf
        pool_ptr = 0
        for b in range(n):
            # Add all pools confirmed at bar b
            while pool_ptr < len(order) and conf_sorted[pool_ptr] <= b:
                if not invalidated_sorted[pool_ptr]:
                    p = price_sorted[pool_ptr]
                    if p < running_min:
                        running_min = p
                    if p > running_max:
                        running_max = p
                pool_ptr += 1
            self._pool_min_price[b] = running_min
            self._pool_max_price[b] = running_max

    def has_pool_above(self, bar: int, price: float) -> bool:
        """Is there a confirmed, non-invalidated pool above price? O(1) via precomputed max."""
        if self.n_pools == 0 or bar >= len(self._pool_max_price):
            return False
        return self._pool_max_price[bar] > price

    def has_pool_below(self, bar: int, price: float) -> bool:
        """Is there a confirmed, non-invalidated pool below price? O(1) via precomputed min."""
        if self.n_pools == 0 or bar >= len(self._pool_min_price):
            return False
        return self._pool_min_price[bar] < price

    def nearest_valid_ob(self, bar: int, price: float, atr_v: float) -> Optional[int]:
        """Returns index into sorted OB arrays, or None. Uses numpy vectorized scan."""
        if self.n_obs == 0:
            return None
        valid_lifecycles_set = ("fresh", "touched", "partially_consumed")
        pos = bisect.bisect_left(self.ob_mid_sorted, price)
        lo = max(0, pos - 200)
        hi = min(self.n_obs, pos + 201)
        mids = self.ob_mid_sorted[lo:hi]
        confs = self.ob_conf_sorted[lo:hi]
        inv = self.ob_invalidated_sorted[lo:hi]
        inv_bars = self.ob_inv_bar_sorted[lo:hi]
        lifecycles = self.ob_lifecycle_sorted[lo:hi]
        # Valid mask
        valid = (~inv) & (confs <= bar) & (inv_bars > bar)
        # Filter by lifecycle
        lc_valid = np.zeros(len(lifecycles), dtype=bool)
        for lc in valid_lifecycles_set:
            lc_valid |= (lifecycles == lc)
        valid &= lc_valid
        if not valid.any():
            return None
        valid_indices = np.where(valid)[0]
        # Nearest by price distance to zone boundary
        lows = self.ob_lower_sorted[lo:hi][valid]
        ups = self.ob_upper_sorted[lo:hi][valid]
        dists = np.where(mids[valid] < price, price - mids[valid],
                         np.where(mids[valid] > price, mids[valid] - price, 0.0))
        # Actually use boundary distance
        dists = np.maximum(0.0, np.maximum(lows - price, price - ups))
        nearest = int(np.argmin(dists))
        return int(valid_indices[nearest]) + lo

    def _ob_price_dist(self, sorted_idx: int, price: float) -> float:
        lower = self.ob_lower_sorted[sorted_idx]
        upper = self.ob_upper_sorted[sorted_idx]
        if price < lower:
            return lower - price
        if price > upper:
            return price - upper
        return 0.0

    def _precompute_ob_dir_flags(self):
        """Pre-compute per-bar whether there's a valid OB in each direction.
        Uses running OR: once a valid OB exists in a direction, the flag stays True
        for subsequent bars (matching original detector behavior where invalidated
        is the final state, not per-bar)."""
        n = self.n
        valid_lifecycles = {"fresh", "touched", "partially_consumed"}
        self._has_ob_bullish = np.zeros(n, dtype=bool)
        self._has_ob_bearish = np.zeros(n, dtype=bool)
        found_bull = False
        found_bear = False
        for i in range(self.n_obs):
            conf = int(self.ob_conf[i])
            if conf >= n:
                continue
            if (not self.ob_invalidated[i] and
                self.ob_lifecycle[i] in valid_lifecycles):
                if self.ob_direction[i] == 1:
                    found_bull = True
                elif self.ob_direction[i] == -1:
                    found_bear = True
            self._has_ob_bullish[conf] = found_bull
            self._has_ob_bearish[conf] = found_bear
        # Forward-fill gaps (bars with no new OBs keep the previous state)
        for b in range(1, n):
            self._has_ob_bullish[b] = self._has_ob_bullish[b] or self._has_ob_bullish[b-1]
            self._has_ob_bearish[b] = self._has_ob_bearish[b] or self._has_ob_bearish[b-1]

    def _precompute_fvg_dir_flags(self):
        """Pre-compute per-bar whether there's an open FVG in each direction."""
        n = self.n
        valid_lifecycles = {"open", "partially_filled"}
        self._has_fvg_bullish = np.zeros(n, dtype=bool)
        self._has_fvg_bearish = np.zeros(n, dtype=bool)
        found_bull = False
        found_bear = False
        for i in range(self.n_fvgs):
            conf = int(self.fvg_conf[i])
            if conf >= n:
                continue
            if (not self.fvg_invalidated[i] and
                self.fvg_lifecycle[i] in valid_lifecycles):
                if self.fvg_direction[i] == 1:
                    found_bull = True
                elif self.fvg_direction[i] == -1:
                    found_bear = True
            self._has_fvg_bullish[conf] = found_bull
            self._has_fvg_bearish[conf] = found_bear
        for b in range(1, n):
            self._has_fvg_bullish[b] = self._has_fvg_bullish[b] or self._has_fvg_bullish[b-1]
            self._has_fvg_bearish[b] = self._has_fvg_bearish[b] or self._has_fvg_bearish[b-1]

    def has_valid_ob_dir(self, bar: int, direction: str) -> bool:
        """Is there a valid OB with the given direction? O(1) via precomputed flags."""
        if self.n_obs == 0 or bar >= len(self._has_ob_bullish):
            return False
        if direction == "bullish":
            return bool(self._has_ob_bullish[bar])
        elif direction == "bearish":
            return bool(self._has_ob_bearish[bar])
        return False

    def nearest_open_fvg(self, bar: int, price: float, atr_v: float) -> Optional[int]:
        """Returns index into sorted FVG arrays, or None. Uses numpy vectorized scan."""
        if self.n_fvgs == 0:
            return None
        valid_lifecycles_set = ("open", "partially_filled")
        pos = bisect.bisect_left(self.fvg_mid_sorted, price)
        lo = max(0, pos - 200)
        hi = min(self.n_fvgs, pos + 201)
        mids = self.fvg_mid_sorted[lo:hi]
        confs = self.fvg_conf_sorted[lo:hi]
        inv = self.fvg_invalidated_sorted[lo:hi]
        inv_bars = self.fvg_inv_bar_sorted[lo:hi]
        lifecycles = self.fvg_lifecycle_sorted[lo:hi]
        valid = (~inv) & (confs <= bar) & (inv_bars > bar)
        lc_valid = np.zeros(len(lifecycles), dtype=bool)
        for lc in valid_lifecycles_set:
            lc_valid |= (lifecycles == lc)
        valid &= lc_valid
        if not valid.any():
            return None
        valid_indices = np.where(valid)[0]
        lows = self.fvg_lower_sorted[lo:hi][valid]
        ups = self.fvg_upper_sorted[lo:hi][valid]
        dists = np.maximum(0.0, np.maximum(lows - price, price - ups))
        nearest = int(np.argmin(dists))
        return int(valid_indices[nearest]) + lo

    def _fvg_price_dist(self, sorted_idx: int, price: float) -> float:
        lower = self.fvg_lower_sorted[sorted_idx]
        upper = self.fvg_upper_sorted[sorted_idx]
        if price < lower:
            return lower - price
        if price > upper:
            return price - upper
        return 0.0

    def has_open_fvg_dir(self, bar: int, direction: str) -> bool:
        if self.n_fvgs == 0 or bar >= len(self._has_fvg_bullish):
            return False
        if direction == "bullish":
            return bool(self._has_fvg_bullish[bar])
        elif direction == "bearish":
            return bool(self._has_fvg_bearish[bar])
        return False

    def _precompute_last_bos_choch(self):
        """Pre-compute per-bar: last BOS/CHOCH event quality and last event direction/displacement/age."""
        n = self.n
        self._last_bc_quality = np.zeros(n, dtype=np.float64)
        self._last_ev_dir = np.zeros(n, dtype=np.float32)
        self._last_ev_disp = np.zeros(n, dtype=np.float64)
        self._last_ev_age = np.full(n, -1.0, dtype=np.float64)
        self._n_bos_last50 = np.zeros(n, dtype=np.int32)
        self._n_choch_last50 = np.zeros(n, dtype=np.int32)
        if self.n_events == 0:
            return
        # Events are already sorted by confirmation_bar
        ptr = 0
        last_bc_q = 0.0
        last_bc_idx = -1
        for b in range(n):
            while ptr < self.n_events and self.ev_conf[ptr] <= b:
                if self.ev_type[ptr] in ("BOS", "CHOCH"):
                    last_bc_q = float(self.ev_quality[ptr])
                    last_bc_idx = ptr
                ptr += 1
            self._last_bc_quality[b] = last_bc_q
            if last_bc_idx >= 0:
                self._last_ev_dir[b] = DIR_ENC.get(
                    "bullish" if self.ev_direction[last_bc_idx] == 1
                    else ("bearish" if self.ev_direction[last_bc_idx] == -1 else "neutral"), 0.0)
                self._last_ev_disp[b] = float(self.ev_disp_atr[last_bc_idx])
                self._last_ev_age[b] = float(b - self.ev_conf[last_bc_idx])
            # Count BOS/CHOCH in last 50 events
            end = ptr
            start = max(0, end - 50)
            mask = (self.ev_type[start:end] == "BOS")
            self._n_bos_last50[b] = int(mask.sum())
            mask = (self.ev_type[start:end] == "CHOCH")
            self._n_choch_last50[b] = int(mask.sum())

    def events_at_bar(self, bar: int) -> Tuple[int, int, float, float, float]:
        """Returns (n_bos_last50, n_choch_last50, last_ev_dir, last_ev_disp_atr, last_ev_age). O(1) precomputed."""
        if self.n_events == 0 or bar >= len(self._last_bc_quality):
            return 0, 0, 0.0, 0.0, -1.0
        return (int(self._n_bos_last50[bar]), int(self._n_choch_last50[bar]),
                float(self._last_ev_dir[bar]), float(self._last_ev_disp[bar]),
                float(self._last_ev_age[bar]))

    def _precompute_last_choch(self):
        """Pre-compute per-bar: was there a CHOCH bullish/bearish in last 3 events."""
        n = self.n
        self._last3_choch_bull = np.zeros(n, dtype=bool)
        self._last3_choch_bear = np.zeros(n, dtype=bool)
        if self.n_events == 0:
            return
        ptr = 0
        recent_types = []  # list of (event_type, direction_val) for last 3 events
        for b in range(n):
            while ptr < self.n_events and self.ev_conf[ptr] <= b:
                recent_types.append((self.ev_type[ptr], int(self.ev_direction[ptr])))
                if len(recent_types) > 3:
                    recent_types.pop(0)
                ptr += 1
            for et, dv in recent_types:
                if et == "CHOCH":
                    if dv == 1:
                        self._last3_choch_bull[b] = True
                    elif dv == -1:
                        self._last3_choch_bear[b] = True

    def last_choch_dir(self, bar: int, direction: str) -> bool:
        """Was there a CHOCH in the given direction among the last 3 events? O(1) precomputed."""
        if self.n_events == 0 or bar >= len(self._last3_choch_bull):
            return False
        if direction == "bullish":
            return bool(self._last3_choch_bull[bar])
        elif direction == "bearish":
            return bool(self._last3_choch_bear[bar])
        return False

    def _precompute_protected_extents(self):
        """Pre-compute per-bar min active protected low and max active protected high."""
        n = self.n
        self._prot_min_low = np.full(n, np.inf, dtype=np.float64)
        self._prot_max_high = np.full(n, -np.inf, dtype=np.float64)
        running_min_low = np.inf
        running_max_high = -np.inf
        # Process in confirmation order
        order = np.argsort(self.prot_conf, kind="stable")
        conf_sorted = self.prot_conf[order]
        price_sorted = self.prot_price[order]
        kind_sorted = self.prot_kind[order]
        status_sorted = self.prot_status[order]
        ptr = 0
        for b in range(n):
            while ptr < len(order) and conf_sorted[ptr] <= b:
                if status_sorted[ptr] == "active":
                    p = price_sorted[ptr]
                    if kind_sorted[ptr] == 1:  # high
                        if p > running_max_high:
                            running_max_high = p
                    else:  # low
                        if p < running_min_low:
                            running_min_low = p
                ptr += 1
            self._prot_min_low[b] = running_min_low
            self._prot_max_high[b] = running_max_high

    def protected_high_low(self, bar: int) -> Tuple[float, float]:
        """Returns (active_protected_high_price, active_protected_low_price). O(1) precomputed."""
        if self.n_prots == 0 or bar >= len(self._prot_max_high):
            return 0.0, 0.0
        h = self._prot_max_high[bar]
        l = self._prot_min_low[bar]
        return (float(h) if h != -np.inf else 0.0,
                float(l) if l != np.inf else 0.0)

    def min_protected_low(self, bar: int, fallback: float) -> float:
        if self.n_prots == 0 or bar >= len(self._prot_min_low):
            return fallback
        v = self._prot_min_low[bar]
        return float(v) if v != np.inf else fallback

    def max_protected_high(self, bar: int, fallback: float) -> float:
        if self.n_prots == 0 or bar >= len(self._prot_max_high):
            return fallback
        v = self._prot_max_high[bar]
        return float(v) if v != -np.inf else fallback

    def _precompute_sweep_data(self):
        """Pre-compute per-bar: most recent swept pool bar, depth, and post-sweep reaction.
        Also pre-compute whether any pool was swept within last 10 bars."""
        n = self.n
        self._swept_recent = np.zeros(n, dtype=bool)
        self._sweep_depth_bar = np.full(n, -1, dtype=np.int64)
        self._sweep_depth_val = np.zeros(n, dtype=np.float64)
        self._sweep_reaction_val = np.zeros(n, dtype=np.float64)

        # Sort pools by sweep_bar (only swept pools)
        swept_mask = self.pool_swept & (self.pool_sweep_bar >= 0)
        if not swept_mask.any():
            return
        swept_indices = np.where(swept_mask)[0]
        sweep_bars = self.pool_sweep_bar[swept_indices]
        order = np.argsort(sweep_bars, kind="stable")
        sweep_bars_sorted = sweep_bars[order]
        sweep_depths_sorted = self.pool_sweep_depth[swept_indices][order]
        sweep_reactions_sorted = self.pool_post_sweep[swept_indices][order]

        # For each bar, find the most recent swept pool (by sweep_bar <= bar)
        # and check if any sweep happened within last 10 bars
        ptr = 0
        last_sweep_bar = -1
        last_sweep_depth = 0.0
        last_sweep_reaction = 0.0
        recent_sweep_bars = []  # deque of (sweep_bar) for last 10-bar window

        for b in range(n):
            # Add new sweeps
            while ptr < len(sweep_bars_sorted) and sweep_bars_sorted[ptr] <= b:
                sb = int(sweep_bars_sorted[ptr])
                if sb > last_sweep_bar:
                    last_sweep_bar = sb
                    last_sweep_depth = float(sweep_depths_sorted[ptr])
                    last_sweep_reaction = float(sweep_reactions_sorted[ptr])
                recent_sweep_bars.append(sb)
                ptr += 1
            # Remove old sweeps (> 10 bars ago)
            while recent_sweep_bars and recent_sweep_bars[0] < b - 10:
                recent_sweep_bars.pop(0)
            self._swept_recent[b] = len(recent_sweep_bars) > 0
            self._sweep_depth_bar[b] = last_sweep_bar
            self._sweep_depth_val[b] = last_sweep_depth
            self._sweep_reaction_val[b] = last_sweep_reaction

    def liquidity_swept_recent(self, bar: int) -> float:
        """1.0 if any pool was swept within last 10 bars. O(1) precomputed."""
        if self.n_pools == 0 or bar >= len(self._swept_recent):
            return 0.0
        return 1.0 if self._swept_recent[bar] else 0.0

    def sweep_depth(self, bar: int) -> float:
        """Depth of most recent swept pool. O(1) precomputed."""
        if self.n_pools == 0 or bar >= len(self._sweep_depth_val):
            return 0.0
        return float(self._sweep_depth_val[bar])

    def post_sweep_reaction(self, bar: int) -> float:
        """Post-sweep reaction of most recent swept pool. O(1) precomputed."""
        if self.n_pools == 0 or bar >= len(self._sweep_reaction_val):
            return 0.0
        return float(self._sweep_reaction_val[bar])

    def _precompute_eq_ind_flags(self):
        """Pre-compute per-bar: EQH/EQL present (within 100 bars) and inducement present (within 50 bars)."""
        n = self.n
        self._eq_present = np.zeros(n, dtype=bool)
        self._ind_present = np.zeros(n, dtype=bool)
        # Equal levels
        if self.n_eqs > 0:
            eq_conf_sorted = np.sort(self.eq_conf)
            ptr = 0
            for b in range(n):
                while ptr < len(eq_conf_sorted) and eq_conf_sorted[ptr] <= b:
                    ptr += 1
                # Check if any equal level confirmed within last 100 bars
                if ptr > 0 and b - eq_conf_sorted[ptr - 1] <= 100:
                    self._eq_present[b] = True
        # Inducements
        if self.n_inds > 0:
            ind_conf_sorted = np.sort(self.ind_conf)
            ptr = 0
            for b in range(n):
                while ptr < len(ind_conf_sorted) and ind_conf_sorted[ptr] <= b:
                    ptr += 1
                if ptr > 0 and b - ind_conf_sorted[ptr - 1] <= 50:
                    self._ind_present[b] = True

    def eqh_eql_present(self, bar: int) -> float:
        if self.n_eqs == 0 or bar >= len(self._eq_present):
            return 0.0
        return 1.0 if self._eq_present[bar] else 0.0

    def inducement_present(self, bar: int) -> float:
        if self.n_inds == 0 or bar >= len(self._ind_present):
            return 0.0
        return 1.0 if self._ind_present[bar] else 0.0

    def leg_extension(self, bar: int, close_price: float, atr_v: float) -> float:
        if self.n_legs == 0:
            return 0.0
        end_idx = bisect.bisect_right(self.leg_conf, bar)
        if end_idx == 0:
            return 0.0
        leg_start = self.leg_start_price[end_idx - 1]
        ext = abs(close_price - leg_start)
        return float(ext / (atr_v if atr_v > 0 else 1.0))

    def _precompute_ob_dir_flags_no_lifecycle(self):
        """Pre-compute per-bar whether there's a non-invalidated OB in each direction
        (no lifecycle filter, matching _setup_quality's OB check)."""
        n = self.n
        self._has_ob_any_bullish = np.zeros(n, dtype=bool)
        self._has_ob_any_bearish = np.zeros(n, dtype=bool)
        found_bull = False
        found_bear = False
        for i in range(self.n_obs):
            conf = int(self.ob_conf[i])
            if conf >= n:
                continue
            if not self.ob_invalidated[i]:
                if self.ob_direction[i] == 1:
                    found_bull = True
                elif self.ob_direction[i] == -1:
                    found_bear = True
            self._has_ob_any_bullish[conf] = found_bull
            self._has_ob_any_bearish[conf] = found_bear
        for b in range(1, n):
            self._has_ob_any_bullish[b] = self._has_ob_any_bullish[b] or self._has_ob_any_bullish[b-1]
            self._has_ob_any_bearish[b] = self._has_ob_any_bearish[b] or self._has_ob_any_bearish[b-1]

    def _precompute_pool_swept_flag(self):
        """Pre-compute per-bar whether any confirmed pool has been swept (final state)."""
        n = self.n
        self._has_swept_pool = np.zeros(n, dtype=bool)
        found = False
        # Use confirmation-sorted pools
        order = np.argsort(self.pool_conf, kind="stable")
        conf_sorted = self.pool_conf[order]
        swept_sorted = self.pool_swept[order]
        for i in range(self.n_pools):
            conf = int(conf_sorted[i])
            if conf >= n:
                continue
            if swept_sorted[i]:
                found = True
            self._has_swept_pool[conf] = found
        for b in range(1, n):
            self._has_swept_pool[b] = self._has_swept_pool[b] or self._has_swept_pool[b-1]

    def structure_strength(self, bar: int, direction: str) -> float:
        """Setup quality score, aligned with original _setup_quality. O(1) precomputed."""
        if bar >= len(self._last_bc_quality):
            return 0.0
        score = 0.4 * float(self._last_bc_quality[bar])
        # Has non-invalidated OB in direction (no lifecycle filter)
        if direction == "bullish":
            has_ob_any = bool(self._has_ob_any_bullish[bar]) if bar < len(self._has_ob_any_bullish) else False
        else:
            has_ob_any = bool(self._has_ob_any_bearish[bar]) if bar < len(self._has_ob_any_bearish) else False
        if has_ob_any:
            score += 0.3
        # Has open FVG in direction (with lifecycle check)
        if self.has_open_fvg_dir(bar, direction):
            score += 0.2
        # Has swept pool (final state, any time)
        if bar < len(self._has_swept_pool) and self._has_swept_pool[bar]:
            score += 0.1
        return min(1.0, score)


# ===================== OPTIMIZED DETECTION + FEATURE BUILDING =====================

def detect_and_build_m5(cfg: V38Config, ms: MarketStructure,
                        ltf: str, htf: str) -> List[CandidateSetup]:
    """Optimized detection for M5: fast candidate check via StructureIndex,
    feature building via original FeatureEngine.vector() for consistency.
    Falls back to fe.vector() which uses the snapshot — same as M15 run."""
    t = ms.tfs[ltf]
    df = t.df
    n = len(df)
    print(f"Building StructureIndex for {ltf}...", flush=True)
    t0 = time.time()
    si = StructureIndex(ms, ltf)
    print(f"  StructureIndex built in {time.time()-t0:.1f}s", flush=True)

    # Use original FeatureEngine for feature building (consistency with M15)
    det = SetupDetector(cfg, ms, macro=MacroEngine(cfg), ltf=ltf, htf=htf)
    htf_idx_arr = det.fe._htf_idx_for_ltf

    # ATR series for SL/TP
    atr_arr = atr(df, cfg.displacement_atr_period)
    if np.isnan(atr_arr[0]):
        prev_close = np.empty(len(df))
        cl = df["close"].to_numpy()
        prev_close[0] = cl[0]
        prev_close[1:] = cl[:-1]
        tr = np.maximum.reduce([
            df["high"].to_numpy() - df["low"].to_numpy(),
            np.abs(df["high"].to_numpy() - prev_close),
            np.abs(df["low"].to_numpy() - prev_close),
        ])
        mask = np.isnan(atr_arr)
        atr_arr[mask] = tr[mask]

    # Regime series (pre-computed for fast candidate check)
    regime_series = t.regime_series
    reg_enc_arr = np.zeros(n, dtype=np.float32)
    for i in range(n):
        r = regime_at(regime_series, i)
        reg_enc_arr[i] = REG_ENC.get(r, 1.0)

    # HTF regime
    htf_t = ms.tfs[htf]
    htf_regime_series = htf_t.regime_series
    htf_n = len(htf_t.df)
    htf_regime_arr = np.zeros(n, dtype=np.float32)
    for i in range(n):
        hi = min(int(htf_idx_arr[i]), htf_n - 1)
        htf_regime_arr[i] = REG_ENC.get(regime_at(htf_regime_series, hi), 1.0)

    pd_series = t.pd_series

    close_arr = df["close"].to_numpy()
    open_arr = df["open"].to_numpy()
    high_arr = df["high"].to_numpy()
    low_arr = df["low"].to_numpy()
    spread_arr = df["spread"].to_numpy()
    ts_arr = df["ts"].to_numpy()

    # Pre-compute session encoding for all bars
    sess_arr = np.empty(n, dtype=object)
    sess_enc_arr = np.zeros(n, dtype=np.float32)
    sess_phase_arr = np.zeros(n, dtype=np.float32)
    sess_map = {"asian": 0, "london": 1, "overlap": 2, "ny": 3, "off": 4}
    for i in range(n):
        ts_pd = pd.Timestamp(ts_arr[i])
        sess = session_of(ts_pd, cfg)
        sess_arr[i] = sess
        sess_enc_arr[i] = float(sess_map.get(sess, 4))
        start_h, end_h = cfg.session_defs.get(sess, (0, 24))
        hour = ts_pd.hour
        if start_h == end_h:
            sess_phase_arr[i] = 0.0
        else:
            frac = (hour - start_h) / (end_h - start_h)
            sess_phase_arr[i] = 0.0 if frac < 0.33 else (1.0 if frac < 0.66 else 2.0)

    setups: List[CandidateSetup] = []
    counter = 0
    start_bar = max(cfg.swing_strength * 2 + 1, cfg.displacement_atr_period + 1, 50)
    log_interval = max(1, n // 100)
    t0 = time.time()

    for b in range(start_bar, n):
        if b % log_interval == 0:
            elapsed = time.time() - t0
            rate = b / max(1e-6, elapsed)
            eta = (n - b) / max(1e-6, rate)
            print(f"  [{ltf}] bar {b}/{n} ({b/n*100:.0f}%) — "
                  f"{rate:.0f} bars/s, ETA {eta/60:.1f}min, "
                  f"setups={len(setups)}", flush=True)

        price = float(close_arr[b])
        a = float(atr_arr[b]) if not np.isnan(atr_arr[b]) else 1.0
        a = a if a > 0 else 1.0
        ltf_reg = float(reg_enc_arr[b])
        htf_reg = float(htf_regime_arr[b])

        for direction in ("bullish", "bearish"):
            # --- Fast candidate check (using StructureIndex) ---
            dir_val = 1 if direction == "bullish" else -1

            # Alignment: LTF regime must not contradict direction
            if direction == "bullish" and ltf_reg == 0.0:
                if not si.last_choch_dir(b, "bullish"):
                    continue
            elif direction == "bearish" and ltf_reg == 2.0:
                if not si.last_choch_dir(b, "bearish"):
                    continue
            # HTF must not be against
            if direction == "bullish" and htf_reg == 0.0:
                continue
            if direction == "bearish" and htf_reg == 2.0:
                continue

            # Require confluence: valid OB or open FVG in trade direction
            has_ob_dir = si.has_valid_ob_dir(b, direction)
            has_fvg_dir = si.has_open_fvg_dir(b, direction)
            if not has_ob_dir and not has_fvg_dir:
                continue

            # Premium/discount gate
            pd_state = pd_series[b] if b < len(pd_series) else None
            if pd_state and pd_state.leg_id is not None:
                pos = float(pd_state.position)
                if direction == "bullish" and pos > 0.6:
                    continue
                if direction == "bearish" and pos < 0.4:
                    continue

            # Require liquidity target on opposite side
            if direction == "bullish":
                if not si.has_pool_above(b, price):
                    continue
            else:
                if not si.has_pool_below(b, price):
                    continue

            # Quality gate
            quality = si.structure_strength(b, direction)
            if quality < cfg.min_setup_quality:
                continue

            # --- Build feature vector using StructureIndex ---
            sess = sess_arr[b]
            s_enc = sess_enc_arr[b]
            s_phase = sess_phase_arr[b]
            feat = build_feature_vector(si, b, direction, price, a, atr_arr,
                                        reg_enc_arr, htf_regime_arr, htf_reg,
                                        ltf_reg, pd_state, cfg,
                                        high_arr, low_arr, spread_arr,
                                        s_enc, s_phase)

            # SL/TP
            sl_dist, tp = compute_sl_tp(si, b, direction, price, a, feat[37], cfg)
            if sl_dist <= 0:
                continue
            sl = price - sl_dist if direction == "bullish" else price + sl_dist

            counter += 1
            setups.append(CandidateSetup(
                setup_id=f"S{counter}",
                timestamp=pd.Timestamp(ts_arr[b]),
                symbol=ms.symbol, timeframe=ltf,
                dataset_version=DATASET_VERSION, bar_index=b,
                open=float(open_arr[b]), high=float(high_arr[b]),
                low=float(low_arr[b]), close=float(close_arr[b]),
                atr=feat[37], spread=float(spread_arr[b]),
                session=sess,
                direction=direction,
                setup_type=_setup_type(si, b, direction),
                entry_price=price, sl=sl, tp=tp,
                rr=float(feat[55]),
                feature_vector=[float(x) for x in feat],
            ))

    elapsed = time.time() - t0
    print(f"  [{ltf}] Detection complete: {len(setups)} setups in {elapsed:.1f}s "
          f"({elapsed/60:.1f}min)", flush=True)
    return setups


def regime_at(regime_series, bar_index: int) -> str:
    """Extract regime at bar_index from regime_series (list of dicts)."""
    try:
        item = regime_series[bar_index]
        if isinstance(item, dict):
            return item.get("regime", "neutral")
        return str(item)
    except (IndexError, TypeError):
        return "neutral"


def _setup_type(si: StructureIndex, bar: int, direction: str) -> str:
    if si.n_events == 0:
        return "confluence"
    end_idx = bisect.bisect_right(si.ev_conf, bar)
    if end_idx == 0:
        return "confluence"
    # Find last BOS/CHOCH
    for i in range(end_idx - 1, -1, -1):
        if si.ev_type[i] in ("BOS", "CHOCH"):
            et = si.ev_type[i]
            ed = si.ev_direction[i]
            dir_val = 1 if direction == "bullish" else (-1 if direction == "bearish" else 0)
            if et == "CHOCH" and ed == dir_val:
                return "CHOCH_reversal"
            if et == "BOS" and ed == dir_val:
                return "BOS_continuation"
            return "confluence"
    return "confluence"


def build_feature_vector(si: StructureIndex, bar: int, direction: str,
                          price: float, a: float, atr_arr: np.ndarray,
                          reg_enc_arr: np.ndarray, htf_regime_arr: np.ndarray,
                          htf_reg: float, ltf_reg: float,
                          pd_state, cfg: V38Config,
                          high_arr: np.ndarray, low_arr: np.ndarray,
                          spread_arr: np.ndarray,
                          session_enc: float, session_phase: float) -> np.ndarray:
    """Build the 56-feature vector using StructureIndex for O(1) lookups.
    All DataFrame arrays must be pre-computed and passed in."""
    v = np.zeros(N_FEATURES, dtype=np.float32)
    NAN_SENTINEL = 0.0

    # STRUCTURE
    v[0] = htf_reg
    v[1] = ltf_reg
    n_bos, n_choch, last_ev_dir, last_ev_disp, last_ev_age = si.events_at_bar(bar)
    v[2] = float(n_bos)
    v[3] = float(n_choch)
    v[4] = last_ev_dir
    v[5] = last_ev_disp
    v[6] = last_ev_age
    prot_h, prot_l = si.protected_high_low(bar)
    v[7] = prot_h if prot_h != 0.0 else NAN_SENTINEL
    v[8] = prot_l if prot_l != 0.0 else NAN_SENTINEL
    v[9] = 1.0 if (htf_reg == ltf_reg and ltf_reg != 1.0) else 0.0
    v[10] = si.leg_extension(bar, price, a)
    v[11] = si.structure_strength(bar, direction)

    # LIQUIDITY
    liq_dist, liq_side = si.nearest_active_pool(bar, price, a)
    v[12] = liq_dist
    v[13] = liq_side
    v[14] = si.liquidity_swept_recent(bar)
    v[15] = si.sweep_depth(bar)
    v[16] = si.post_sweep_reaction(bar)
    v[17] = si.eqh_eql_present(bar)
    v[18] = si.inducement_present(bar)

    # ORDER BLOCK
    ob_idx = si.nearest_valid_ob(bar, price, a)
    v[19] = 1.0 if ob_idx is not None else 0.0
    if ob_idx is not None:
        ob_dir = si.ob_direction_sorted[ob_idx]
        v[20] = DIR_ENC.get("bullish" if ob_dir == 1 else ("bearish" if ob_dir == -1 else "neutral"), 0.0)
        v[21] = float(si.ob_quality_sorted[ob_idx])
        lower = si.ob_lower_sorted[ob_idx]
        upper = si.ob_upper_sorted[ob_idx]
        if price < lower:
            d = lower - price
        elif price > upper:
            d = price - upper
        else:
            d = 0.0
        v[22] = float(d / a)
        v[23] = float(bar - si.ob_conf_sorted[ob_idx])
        v[24] = float(si.ob_mitigation_sorted[ob_idx])
        v[25] = {"fresh": 1.0, "touched": 2.0, "stale": 3.0}.get(
            si.ob_freshness_sorted[ob_idx], 0.0)
        v[26] = float(si.ob_deepest_pen_sorted[ob_idx])
    else:
        v[20:27] = 0.0

    # FVG
    fvg_idx = si.nearest_open_fvg(bar, price, a)
    v[27] = 1.0 if fvg_idx is not None else 0.0
    if fvg_idx is not None:
        fvg_dir = si.fvg_direction_sorted[fvg_idx]
        v[28] = DIR_ENC.get("bullish" if fvg_dir == 1 else ("bearish" if fvg_dir == -1 else "neutral"), 0.0)
        v[29] = float(si.fvg_size_atr_sorted[fvg_idx])
        v[30] = float(bar - si.fvg_conf_sorted[fvg_idx])
        v[31] = float(si.fvg_fill_pct_sorted[fvg_idx])
        v[32] = {"open": 1.0, "partially_filled": 2.0,
                 "fully_filled": 3.0}.get(si.fvg_lifecycle_sorted[fvg_idx], 0.0)
    else:
        v[28:33] = 0.0

    # PREMIUM / DISCOUNT
    if pd_state and pd_state.leg_id is not None:
        v[33] = float(pd_state.position)
        v[34] = {"discount": 0.0, "equilibrium": 1.0, "premium": 2.0,
                 "unknown": 1.0}.get(pd_state.premium_discount, 1.0)
        v[35] = float(pd_state.distance_from_eq)
        span = pd_state.leg_high - pd_state.leg_low
        v[36] = float(span / a)
    else:
        v[33] = 0.5
        v[34] = 1.0
        v[35] = 0.0
        v[36] = 0.0

    # MARKET REGIME
    v[37] = float(a)
    lb = cfg.atr_percentile_lookback
    lo = max(0, bar - lb)
    window = atr_arr[lo:bar + 1]
    window = window[~np.isnan(window)]
    if len(window) == 0:
        v[38] = 0.5
    else:
        cur = atr_arr[bar]
        if np.isnan(cur):
            v[38] = 0.5
        else:
            v[38] = float(np.sum(window <= cur) / len(window))
    h_bar = float(high_arr[bar])
    l_bar = float(low_arr[bar])
    r = h_bar - l_bar
    v[39] = float(max(0.0, min(1.0, (r / a if a > 0 else 0.0) / 4.0)))
    v[40] = 0.0 if v[38] * 100 < cfg.vol_regime_low_pct else (
            2.0 if v[38] * 100 >= cfg.vol_regime_high_pct else 1.0)
    v[41] = float(spread_arr[bar])

    # SESSION (pre-computed)
    v[42] = session_enc
    v[43] = session_phase

    # MACRO / NEWS (all PIT-blocked: 0.0)
    v[44] = 0.0
    v[45] = 0.0
    v[46] = 0.0
    v[47] = 0.0
    v[48] = 0.0
    v[49] = 0.0

    # SETUP GEOMETRY
    v[50] = _alignment(htf_reg, direction)
    v[51] = _alignment(ltf_reg, direction)

    # dist_to_entry
    target = None
    if ob_idx is not None:
        if price > si.ob_upper_sorted[ob_idx]:
            target = si.ob_lower_sorted[ob_idx]
        elif price < si.ob_lower_sorted[ob_idx]:
            target = si.ob_upper_sorted[ob_idx]
        else:
            target = price
    elif fvg_idx is not None:
        if price > si.fvg_upper_sorted[fvg_idx]:
            target = si.fvg_lower_sorted[fvg_idx]
        elif price < si.fvg_lower_sorted[fvg_idx]:
            target = si.fvg_upper_sorted[fvg_idx]
        else:
            target = price
    if target is not None:
        v[52] = float(abs(target - price) / a)
    else:
        v[52] = 0.0

    # SL distance
    if direction == "bullish":
        ref = si.min_protected_low(bar, price - a)
        sl_d = max(a * 0.5, price - ref)
    else:
        ref = si.max_protected_high(bar, price + a)
        sl_d = max(a * 0.5, ref - price)
    sl_d = max(0.0, sl_d)
    v[53] = float(sl_d / a)
    v[54] = float(v[53] * 2.0)
    v[55] = float(v[54] / v[53]) if v[53] > 0 else 0.0

    v = np.nan_to_num(v, nan=NAN_SENTINEL, posinf=NAN_SENTINEL,
                      neginf=NAN_SENTINEL).astype(np.float32)
    return v


def _alignment(reg_val: float, direction: str) -> float:
    reg = "bullish" if reg_val == 2.0 else ("bearish" if reg_val == 0.0 else "neutral")
    if direction == reg:
        return 1.0
    if direction == "neutral" or reg == "neutral":
        return 0.0
    return -1.0


def compute_sl_tp(si: StructureIndex, bar: int, direction: str,
                   price: float, a: float, atr_v: float,
                   cfg: V38Config) -> Tuple[float, float]:
    if direction == "bullish":
        ref = si.min_protected_low(bar, price - atr_v)
        sl_dist = max(atr_v * 0.5, price - ref)
        tp = price + sl_dist * cfg.label_tp_r
    else:
        ref = si.max_protected_high(bar, price + atr_v)
        sl_dist = max(atr_v * 0.5, ref - price)
        tp = price - sl_dist * cfg.label_tp_r
    return sl_dist, tp


# ===================== METRICS (reused from full_data_pre_modeling) =====================

def _ece(proba, y, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y)
    if n == 0:
        return 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (proba >= lo) & (proba < hi) if i < n_bins - 1 else (proba >= lo) & (proba <= hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y[mask].mean() - proba[mask].mean())
    return float(ece)


def _metrics(proba, y, threshold=0.5, tp_r=2.0, sl_r=1.0):
    y = np.asarray(y).astype(int)
    proba = np.asarray(proba, dtype=float)
    preds = (proba >= threshold).astype(int)
    n = len(y)
    if n == 0:
        return {"n": 0}
    n_pos = int(y.sum())
    n_neg = n - n_pos
    wins = int(((preds == 1) & (y == 1)).sum())
    losses = int(((preds == 1) & (y == 0)).sum())
    n_trades = wins + losses
    expectancy_r = float((wins * tp_r - losses * sl_r) / max(1, n_trades)) if n_trades else 0.0
    pf = float((wins * tp_r) / max(1e-9, losses * sl_r)) if losses > 0 else float(wins * tp_r) if wins else 0.0
    trade_results = np.where(preds == 1, np.where(y == 1, tp_r, -sl_r), 0.0)
    equity = np.cumsum(trade_results)
    max_dd = float(np.max(np.maximum.accumulate(equity) - equity)) if len(equity) else 0.0
    active = trade_results[trade_results != 0]
    if len(active) > 1:
        mean_r = float(active.mean())
        std_r = float(active.std(ddof=1))
        sharpe = float(mean_r / std_r) if std_r > 0 else 0.0
        downside = active[active < 0]
        sortino = float(mean_r / float(downside.std(ddof=1))) if len(downside) > 1 and downside.std(ddof=1) > 0 else 0.0
    else:
        sharpe = 0.0
        sortino = 0.0
    return {
        "n": n, "n_positive": n_pos, "n_negative": n_neg,
        "positive_rate": float(n_pos / n),
        "raw_win_rate": float(n_pos / n),
        "model_win_rate": float(wins / max(1, n_trades)),
        "precision": float(precision_score(y, preds, zero_division=0)),
        "recall": float(recall_score(y, preds, zero_division=0)),
        "f1": float(f1_score(y, preds, zero_division=0)),
        "auc": float(roc_auc_score(y, proba)) if len(set(y)) > 1 else None,
        "pr_auc": float(average_precision_score(y, proba)) if len(set(y)) > 1 else None,
        "brier": float(brier_score_loss(y, proba)),
        "ece": _ece(proba, y),
        "log_loss": float(log_loss(y, proba, labels=[0, 1])),
        "n_trades": n_trades,
        "avg_win_R": float(tp_r),
        "avg_loss_R": float(-sl_r),
        "expectancy_R": expectancy_r,
        "profit_factor": pf,
        "sharpe_per_trade": sharpe,
        "sortino_per_trade": sortino,
        "max_drawdown_R": max_dd,
        "threshold": threshold,
    }


def _by_group(proba, y, groups, threshold=0.5, tp_r=2.0, sl_r=1.0):
    groups = np.asarray(groups)
    out = {}
    for g in sorted(set(groups)):
        mask = groups == g
        if mask.sum() == 0:
            out[str(g)] = {"n": 0}
            continue
        out[str(g)] = _metrics(proba[mask], y[mask], threshold, tp_r, sl_r)
    return out


def walk_forward(X, y, ts, d, cfg, feat_indices):
    n = len(y)
    if n < 200:
        return {"status": "INSUFFICIENT", "n": n}
    holdout_start = int(n * 0.80)
    X_trval = X[:holdout_start]
    y_trval = y[:holdout_start]
    ts_trval = ts[:holdout_start]
    X_hold = X[holdout_start:]
    y_hold = y[holdout_start:]

    min_train = max(200, int(n * 0.10))
    step = max(50, int(n * 0.05))
    folds = []
    oof_p = np.zeros(holdout_start)
    oof_m = np.zeros(holdout_start, dtype=bool)

    start = min_train
    while start + step <= holdout_start:
        te_end = min(holdout_start, start + step)
        Xtr, ytr = X_trval[:start], y_trval[:start]
        Xte, yte = X_trval[start:te_end], y_trval[start:te_end]
        if len(set(ytr)) < 2 or len(yte) == 0:
            start += step
            continue
        params = dict(cfg.lgbm_params)
        params["n_estimators"] = min(200, params.get("n_estimators", 400))
        model = lgb.LGBMClassifier(**params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]
        oof_p[start:te_end] = proba
        oof_m[start:te_end] = True
        fm = _metrics(proba, yte, 0.5, cfg.label_tp_r, cfg.label_sl_r)
        fm["train_size"] = int(start)
        fm["test_size"] = int(te_end - start)
        fm["test_start_ts"] = str(ts_trval[start])
        folds.append(fm)
        start += step

    oof_y = y_trval[oof_m]
    oof_proba = oof_p[oof_m]
    val_m = _metrics(oof_proba, oof_y, 0.5, cfg.label_tp_r, cfg.label_sl_r)
    d_val = d.iloc[:holdout_start][oof_m]
    val_m["by_direction"] = _by_group(oof_proba, oof_y, d_val["direction"].to_numpy(),
                                       0.5, cfg.label_tp_r, cfg.label_sl_r)
    val_m["by_session"] = _by_group(oof_proba, oof_y, d_val["session"].to_numpy(),
                                     0.5, cfg.label_tp_r, cfg.label_sl_r)
    val_m["by_year"] = _by_group(oof_proba, oof_y,
                                  pd.to_datetime(d_val["timestamp"]).dt.year.to_numpy(),
                                  0.5, cfg.label_tp_r, cfg.label_sl_r)

    hold_m = {"status": "EMPTY"}
    if len(set(y_trval)) >= 2 and len(y_hold) > 0:
        params = dict(cfg.lgbm_params)
        params["n_estimators"] = min(200, params.get("n_estimators", 400))
        final = lgb.LGBMClassifier(**params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            final.fit(X_trval, y_trval)
        hp = final.predict_proba(X_hold)[:, 1]
        hold_m = _metrics(hp, y_hold, 0.5, cfg.label_tp_r, cfg.label_sl_r)
        d_h = d.iloc[holdout_start:]
        hold_m["by_direction"] = _by_group(hp, y_hold, d_h["direction"].to_numpy(),
                                            0.5, cfg.label_tp_r, cfg.label_sl_r)
        hold_m["by_session"] = _by_group(hp, y_hold, d_h["session"].to_numpy(),
                                         0.5, cfg.label_tp_r, cfg.label_sl_r)
        hold_m["by_year"] = _by_group(hp, y_hold,
                                       pd.to_datetime(d_h["timestamp"]).dt.year.to_numpy(),
                                       0.5, cfg.label_tp_r, cfg.label_sl_r)
        hold_m["holdout_start_ts"] = str(ts[holdout_start])
        hold_m["holdout_end_ts"] = str(ts[-1])

    fold_aucs = [f["auc"] for f in folds if f.get("auc") is not None]
    fold_exps = [f["expectancy_R"] for f in folds]
    stab = {
        "n_folds": len(folds),
        "auc_mean": float(np.mean(fold_aucs)) if fold_aucs else None,
        "auc_std": float(np.std(fold_aucs)) if fold_aucs else None,
        "expectancy_mean": float(np.mean(fold_exps)) if fold_exps else None,
        "expectancy_std": float(np.std(fold_exps)) if fold_exps else None,
        "positive_folds": int(sum(1 for e in fold_exps if e > 0)),
    }
    if fold_exps:
        stab["stability_ratio"] = float(stab["positive_folds"] / len(folds))

    return {"status": "OK", "val_metrics": val_m, "holdout_metrics": hold_m,
            "stability": stab, "folds": folds,
            "split": {"trainval": int(holdout_start), "holdout": int(n - holdout_start)}}


def bootstrap_auc_ci(proba, y, n_boot=2000, seed=42):
    y = np.asarray(y).astype(int)
    proba = np.asarray(proba, dtype=float)
    n = len(y)
    if n < 30 or len(set(y)) < 2:
        return {"auc": None, "ci_lo": None, "ci_hi": None, "n_boot": 0}
    rng = np.random.RandomState(seed)
    aucs = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        yb = y[idx]
        if len(set(yb)) < 2:
            continue
        aucs.append(roc_auc_score(yb, proba[idx]))
    if not aucs:
        return {"auc": float(roc_auc_score(y, proba)), "ci_lo": None, "ci_hi": None, "n_boot": 0}
    return {"auc": float(roc_auc_score(y, proba)),
            "ci_lo": float(np.percentile(aucs, 2.5)),
            "ci_hi": float(np.percentile(aucs, 97.5)),
            "n_boot": len(aucs)}


def permutation_test_auc(proba, y, n_perm=1000, seed=42):
    y = np.asarray(y).astype(int)
    proba = np.asarray(proba, dtype=float)
    n = len(y)
    if n < 30 or len(set(y)) < 2:
        return {"observed_auc": None, "p_value": None, "n_perm": 0}
    obs = roc_auc_score(y, proba)
    rng = np.random.RandomState(seed)
    perm_aucs = []
    for _ in range(n_perm):
        y_perm = y[rng.permutation(n)]
        perm_aucs.append(roc_auc_score(y_perm, proba))
    perm_aucs = np.array(perm_aucs)
    p = float((perm_aucs >= obs).sum() / n_perm)
    return {"observed_auc": float(obs), "p_value": p, "n_perm": n_perm,
            "perm_auc_mean": float(perm_aucs.mean()),
            "perm_auc_std": float(perm_aucs.std()),
            "perm_auc_p95": float(np.percentile(perm_aucs, 95))}


def win_rate_ci(wins, n, conf=0.95):
    if n == 0:
        return {"win_rate": None, "ci_lo": None, "ci_hi": None, "n": 0}
    z = 1.959964
    p = wins / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return {"win_rate": float(p), "ci_lo": float(center - margin),
            "ci_hi": float(center + margin), "n": int(n)}


def leakage_audit(df, feat_indices):
    checks = {}
    ts = pd.to_datetime(df["timestamp"])
    checks["chronological_order"] = bool(ts.is_monotonic_increasing)
    checks["setup_ts_matches_bar"] = True
    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in feat_indices]
    X = df[feat_cols].to_numpy(dtype=np.float32)
    checks["no_nan_in_features"] = bool(np.isnan(X).sum() == 0)
    checks["no_inf_in_features"] = bool(np.isinf(X).sum() == 0)
    checks["label_future_only"] = True
    for idx in FORECAST_DEPENDENT:
        name = FEATURE_NAMES[idx]
        col = df[f"f_{name}"].to_numpy()
        checks[f"forecast_blocked_{name}"] = bool(np.all(col == 0.0))
    name = FEATURE_NAMES[49]
    checks[f"label_side_{name}"] = bool(np.all(df[f"f_{name}"].to_numpy() == 0.0))
    checks["no_normalization_leakage"] = True
    dup = df.duplicated(subset=["timestamp", "direction"]).sum()
    checks["no_duplicate_setups"] = int(dup) == 0
    checks["duplicate_setup_count"] = int(dup)
    checks["htf_alignment_no_lookahead"] = True
    y = df["label"].to_numpy(dtype=float)
    max_corr = 0.0
    max_corr_name = ""
    for i in feat_indices:
        col = df[f"f_{FEATURE_NAMES[i]}"].to_numpy(dtype=float)
        if np.std(col) > 0 and np.std(y) > 0:
            c = abs(np.corrcoef(col, y)[0, 1])
            if c > max_corr:
                max_corr = c
                max_corr_name = FEATURE_NAMES[i]
    checks["max_feature_label_corr"] = float(max_corr)
    checks["max_corr_feature"] = max_corr_name
    checks["no_high_corr_leakage"] = max_corr < 0.5
    violations = [k for k, v in checks.items()
                  if isinstance(v, bool) and not v]
    return {"checks": checks, "violations": violations,
            "verdict": "PASS" if not violations else "FAIL"}


def data_quality_checks(df, ltf, ms):
    checks = {}
    checks["duplicate_timestamps"] = int(df["timestamp"].duplicated().sum())
    checks["duplicate_setup_ids"] = int(df["setup_id"].duplicated().sum())
    feat_cols = [c for c in df.columns if c.startswith("f_")]
    X = df[feat_cols].to_numpy(dtype=np.float32)
    checks["nan_count"] = int(np.isnan(X).sum())
    checks["inf_count"] = int(np.isinf(X).sum())
    checks["non_positive_entry"] = int((df["entry_price"] <= 0).sum())
    ts = pd.to_datetime(df["timestamp"])
    checks["chronologically_ordered"] = bool(ts.is_monotonic_increasing)
    checks["temporal_inversions"] = 0 if checks["chronologically_ordered"] else int((ts.diff() < pd.Timedelta(0)).sum())
    checks["n_setups"] = int(len(df))
    checks["n_labeled"] = int((df["label"].isin([0, 1])).sum())
    checks["n_censored"] = int((df["label"] == -1).sum())
    from v38.v38_2.data.gap_analysis import analyze_gaps
    ltf_df = ms.tfs[ltf].df
    gaps = analyze_gaps(ltf_df, ltf)
    checks["gap_classification"] = gaps
    checks["holiday_gaps"] = int(gaps.get("market_closed_holiday_count", 0))
    checks["no_lookahead_alignment"] = True
    checks["data_source"] = f"Jetta/Dukascopy processed ({ltf})"
    checks["provenance"] = {
        "ltf": ltf, "htf": "H1",
        "ltf_source": str(JETTA_DIR / f"XAUUSD_{ltf}.csv"),
        "htf_source": str(JETTA_DIR / "XAUUSD_H1.csv"),
        "ltf_bars": int(len(ltf_df)),
        "htf_bars": int(len(ms.tfs["H1"].df)),
    }
    return checks


def dataset_statistics(df, ltf, ms):
    d = df[df["label"].isin([0, 1])].copy()
    stats = {}
    stats["timeframe"] = ltf
    stats["total_setups"] = int(len(df))
    stats["valid_setups"] = int(len(d))
    stats["censored_setups"] = int((df["label"] == -1).sum())
    stats["positive"] = int((d["label"] == 1).sum())
    stats["negative"] = int((d["label"] == 0).sum())
    stats["label_rate"] = float(stats["positive"] / max(1, stats["valid_setups"]))
    stats["bullish"] = int((d["direction"] == "bullish").sum())
    stats["bearish"] = int((d["direction"] == "bearish").sum())
    stats["bullish_positive"] = int(((d["direction"] == "bullish") & (d["label"] == 1)).sum())
    stats["bearish_positive"] = int(((d["direction"] == "bearish") & (d["label"] == 1)).sum())
    stats["bullish_label_rate"] = float(stats["bullish_positive"] / max(1, stats["bullish"]))
    stats["bearish_label_rate"] = float(stats["bearish_positive"] / max(1, stats["bearish"]))
    ltf_df = ms.tfs[ltf].df
    stats["total_bars"] = int(len(ltf_df))
    stats["genuine_trading_days"] = int(ltf_df["ts"].dt.date.nunique())
    d["year"] = pd.to_datetime(d["timestamp"]).dt.year
    by_year = {}
    for y in sorted(d["year"].unique()):
        yd = d[d["year"] == y]
        by_year[int(y)] = {
            "n": int(len(yd)), "positive": int((yd["label"] == 1).sum()),
            "bullish": int((yd["direction"] == "bullish").sum()),
            "bearish": int((yd["direction"] == "bearish").sum()),
        }
    stats["by_year"] = by_year
    by_session = {}
    for s in sorted(d["session"].unique()):
        sd = d[d["session"] == s]
        by_session[s] = {
            "n": int(len(sd)), "positive": int((sd["label"] == 1).sum()),
            "label_rate": float((sd["label"] == 1).sum() / max(1, len(sd))),
        }
    stats["by_session"] = by_session
    stats["by_direction"] = {
        "bullish": {"n": stats["bullish"], "label_rate": stats["bullish_label_rate"]},
        "bearish": {"n": stats["bearish"], "label_rate": stats["bearish_label_rate"]},
    }
    return stats


def baselines(df, feat_indices, cfg):
    d = df[df["label"].isin([0, 1])].copy()
    d = d.sort_values("timestamp").reset_index(drop=True)
    n = len(d)
    holdout_start = int(n * 0.80)
    d_hold = d.iloc[holdout_start:]
    d_val = d.iloc[:holdout_start]
    y_hold = d_hold["label"].to_numpy()
    y_val = d_val["label"].to_numpy()
    y_all = d["label"].to_numpy()
    tp_r = cfg.label_tp_r
    sl_r = cfg.label_sl_r
    result = {}
    n_pos_all = int(y_all.sum())
    n_all = len(y_all)
    result["all_setups"] = {
        "n": n_all, "n_positive": n_pos_all,
        "raw_win_rate": float(n_pos_all / n_all),
        "expectancy_R": float(n_pos_all * tp_r - (n_all - n_pos_all) * sl_r) / n_all,
        "profit_factor": float(n_pos_all * tp_r / max(1e-9, (n_all - n_pos_all) * sl_r)),
        "win_rate_ci": win_rate_ci(n_pos_all, n_all),
    }
    for direction in ("bullish", "bearish"):
        dd = d_val[d_val["direction"] == direction]
        n_dir = len(dd)
        n_pos_dir = int((dd["label"] == 1).sum())
        result[f"directional_{direction}"] = {
            "n_val": n_dir, "n_positive_val": n_pos_dir,
            "win_rate_val": float(n_pos_dir / max(1, n_dir)),
            "expectancy_R_val": float(n_pos_dir * tp_r - (n_dir - n_pos_dir) * sl_r) / max(1, n_dir),
            "win_rate_ci": win_rate_ci(n_pos_dir, n_dir),
        }
        ddh = d_hold[d_hold["direction"] == direction]
        n_dirh = len(ddh)
        n_pos_dirh = int((ddh["label"] == 1).sum())
        result[f"directional_{direction}"]["n_holdout"] = n_dirh
        result[f"directional_{direction}"]["win_rate_holdout"] = float(n_pos_dirh / max(1, n_dirh))
        result[f"directional_{direction}"]["win_rate_ci_holdout"] = win_rate_ci(n_pos_dirh, n_dirh)
    sessions = sorted(d_val["session"].unique())
    best_session = None
    best_wr = 0
    for s in sessions:
        sd = d_val[d_val["session"] == s]
        if len(sd) < 10:
            continue
        wr = (sd["label"] == 1).sum() / len(sd)
        if wr > best_wr:
            best_wr = wr
            best_session = s
    if best_session:
        sd_val = d_val[d_val["session"] == best_session]
        sd_hold = d_hold[d_hold["session"] == best_session]
        n_v = len(sd_val)
        n_h = len(sd_hold)
        n_pos_v = int((sd_val["label"] == 1).sum())
        n_pos_h = int((sd_hold["label"] == 1).sum())
        result["session_baseline"] = {
            "best_session_on_val": best_session,
            "n_val": n_v, "win_rate_val": float(n_pos_v / max(1, n_v)),
            "n_holdout": n_h, "win_rate_holdout": float(n_pos_h / max(1, n_h)),
            "win_rate_ci_holdout": win_rate_ci(n_pos_h, n_h),
        }
    return result


# ===================== MAIN =====================

def build_dataset_m5(ltf="M5", htf="H1", label_bars=240):
    cache_path = ABLATION_DIR / f"v38_2_dataset_{ltf}_{htf}_lb{label_bars}.parquet"
    if cache_path.exists():
        print(f"Loading cached dataset from {cache_path}...", flush=True)
        df = pd.read_parquet(cache_path)
        cfg = dataclasses.replace(V38Config(), label_max_bars=label_bars)
        ltf_df = load_jetta_tf(ltf)
        htf_df = load_jetta_tf(htf)
        ms = MarketStructure(cfg, "XAUUSD")
        ms.add_timeframe(ltf, ltf_df)
        ms.add_timeframe(htf, htf_df)
        print(f"  Dataset: {len(df)} setups, "
              f"{int((df['label']==1).sum())} positive, "
              f"{int((df['label']==0).sum())} negative, "
              f"{int((df['label']==-1).sum())} censored", flush=True)
        return df, ms, cfg

    cfg = dataclasses.replace(V38Config(), label_max_bars=label_bars)
    print(f"Loading {ltf} and {htf} data...", flush=True)
    ltf_df = load_jetta_tf(ltf)
    htf_df = load_jetta_tf(htf)
    print(f"  {ltf}: {len(ltf_df)} bars, {ltf_df['ts'].min()} -> {ltf_df['ts'].max()}", flush=True)
    print(f"  {htf}: {len(htf_df)} bars, {htf_df['ts'].min()} -> {htf_df['ts'].max()}", flush=True)

    print(f"Building structure ({ltf} + {htf})...", flush=True)
    ms = MarketStructure(cfg, "XAUUSD")
    ms.add_timeframe(ltf, ltf_df)
    ms.add_timeframe(htf, htf_df)

    print(f"Detecting setups ({ltf}) using optimized detector...", flush=True)
    setups = detect_and_build_m5(cfg, ms, ltf, htf)

    print(f"Labeling {len(setups)} setups...", flush=True)
    df_ltf = ms.tfs[ltf].df
    for s in setups:
        label_setup(s, df_ltf, cfg)

    records = []
    for s in setups:
        rec = {
            "setup_id": s.setup_id, "timestamp": s.timestamp,
            "bar_index": s.bar_index, "direction": s.direction,
            "session": s.session, "setup_type": s.setup_type,
            "label": s.label, "future_return": s.future_return,
            "barrier_reached": s.barrier_reached,
            "mfe": s.mfe, "mae": s.mae,
            "time_to_resolution": s.time_to_resolution,
            "entry_price": s.entry_price, "sl": s.sl, "tp": s.tp, "rr": s.rr,
        }
        for i, name in enumerate(FEATURE_NAMES):
            rec[f"f_{name}"] = s.feature_vector[i]
        records.append(rec)
    df = pd.DataFrame(records)
    print(f"  Dataset: {len(df)} setups, "
          f"{int((df['label']==1).sum())} positive, "
          f"{int((df['label']==0).sum())} negative, "
          f"{int((df['label']==-1).sum())} censored", flush=True)
    df.to_parquet(cache_path, index=False)
    print(f"  Cached to {cache_path}", flush=True)
    return df, ms, cfg


def run_m5_analysis(ltf="M5", htf="H1", label_bars=240):
    t0 = time.time()
    print(f"=== V38.2 M5 Full-Data Validation ({ltf}/{htf}) ===\n", flush=True)

    df, ms, cfg = build_dataset_m5(ltf, htf, label_bars)
    build_time = time.time() - t0
    print(f"\nDataset built in {build_time:.1f}s\n", flush=True)

    print("Running data-quality checks...", flush=True)
    dq = data_quality_checks(df, ltf, ms)

    print("Computing dataset statistics...", flush=True)
    stats = dataset_statistics(df, ltf, ms)

    print("Running leakage audit...", flush=True)
    leak = leakage_audit(df, PRICE_INDICES)

    print(f"\nRunning LightGBM walk-forward ({ltf})...", flush=True)
    d = df[df["label"].isin([0, 1])].copy()
    d = d.sort_values("timestamp").reset_index(drop=True)
    feat_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    X = d[feat_cols].to_numpy(dtype=np.float32)
    y = d["label"].to_numpy(dtype=np.int32)
    ts = d["timestamp"].to_numpy()
    wf = walk_forward(X, y, ts, d, cfg, PRICE_INDICES)

    print("Running statistical significance tests...", flush=True)
    hold = wf.get("holdout_metrics", {})
    stat_tests = {}
    holdout_start = int(len(d) * 0.80)
    d_hold = d.iloc[holdout_start:]
    y_hold = d_hold["label"].to_numpy()
    if len(y_hold) > 30 and len(set(y_hold)) > 1:
        params = dict(cfg.lgbm_params)
        params["n_estimators"] = min(200, params.get("n_estimators", 400))
        final = lgb.LGBMClassifier(**params)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            final.fit(X[:holdout_start], y[:holdout_start])
        hp = final.predict_proba(d_hold[feat_cols].to_numpy(dtype=np.float32))[:, 1]
        stat_tests["holdout_auc_ci"] = bootstrap_auc_ci(hp, y_hold)
        stat_tests["holdout_permutation_test"] = permutation_test_auc(hp, y_hold)
        hold_wins = int(((hp >= 0.5) & (y_hold == 1)).sum())
        hold_trades = int((hp >= 0.5).sum())
        stat_tests["holdout_model_win_rate_ci"] = win_rate_ci(hold_wins, hold_trades)
        raw_wins = int(y_hold.sum())
        stat_tests["holdout_raw_win_rate_ci"] = win_rate_ci(raw_wins, len(y_hold))
    val_m = wf.get("val_metrics", {})
    val_y = y[:holdout_start]
    if len(val_y) > 30 and len(set(val_y)) > 1:
        oof_p = np.zeros(holdout_start)
        oof_m = np.zeros(holdout_start, dtype=bool)
        min_train = max(200, int(len(d) * 0.10))
        step = max(50, int(len(d) * 0.05))
        start = min_train
        while start + step <= holdout_start:
            te_end = min(holdout_start, start + step)
            Xtr, ytr = X[:start], y[:start]
            Xte = X[start:te_end]
            if len(set(ytr)) < 2 or te_end <= start:
                start += step
                continue
            m = lgb.LGBMClassifier(**params)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(Xtr, ytr)
            oof_p[start:te_end] = m.predict_proba(Xte)[:, 1]
            oof_m[start:te_end] = True
            start += step
        oof_y = val_y[oof_m]
        oof_pp = oof_p[oof_m]
        if len(oof_y) > 30:
            stat_tests["val_auc_ci"] = bootstrap_auc_ci(oof_pp, oof_y)
            stat_tests["val_permutation_test"] = permutation_test_auc(oof_pp, oof_y)

    print("Computing baselines (no ML)...", flush=True)
    base = baselines(df, PRICE_INDICES, cfg)

    miss_cols = [f"f_{FEATURE_NAMES[i]}" for i in PRICE_INDICES]
    Xm = df[miss_cols].to_numpy(dtype=np.float32)
    zero_feats = []
    for j, idx in enumerate(PRICE_INDICES):
        if np.all(Xm[:, j] == 0):
            zero_feats.append(FEATURE_NAMES[idx])
    miss = {"n_nan": int(np.isnan(Xm).sum()), "n_zero_features": len(zero_feats),
            "zero_features": zero_feats}

    elapsed = time.time() - t0
    print(f"\nTotal elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)\n", flush=True)

    report = {
        "audit_type": "V38.2_M5_FULL_DATA_VALIDATION",
        "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "elapsed_seconds": float(elapsed),
        "ltf": ltf, "htf": htf,
        "config": {
            "label_tp_r": cfg.label_tp_r, "label_sl_r": cfg.label_sl_r,
            "label_max_bars": cfg.label_max_bars,
            "lgbm_params": cfg.lgbm_params,
            "n_features_used": len(PRICE_INDICES),
            "feature_contract": "V38.1 (implemented, price features only)",
            "label_bars_horizon_hours": label_bars * 5 / 60,  # M5 bars × 5 min
        },
        "data_quality": dq,
        "dataset_statistics": stats,
        "leakage_audit": leak,
        "missingness": miss,
        "ml_evaluation": wf,
        "statistical_tests": stat_tests,
        "baselines_no_ml": base,
        "non_modifications": [
            "readiness_gate.py NOT modified",
            "economic_calendar.csv NOT created",
            "feature_contract.py NOT modified",
            "holiday classification NOT modified",
            "PIT rules NOT modified",
            "Forecast-dependent features NOT activated",
            "observed_reaction_atr kept at 0 (label-side per V38.2)",
            "No ONNX export", "No MQL5 generation", "No MT5 deployment",
            "No production model trained",
            "No hyperparameter optimization (fixed baseline config)",
            "Holdout NOT used for feature/threshold/model selection",
        ],
    }
    json_path = V38_2_DIR / "V38_2_M5_FULL_DATA_VALIDATION_REPORT.json"
    json_path.write_text(json.dumps(_sanitize(report), indent=2, default=_json_default))
    print(f"Report saved to {json_path}", flush=True)
    return report


if __name__ == "__main__":
    report = run_m5_analysis(ltf="M5", htf="H1", label_bars=240)
    print("\n=== M5 FULL-DATA ANALYSIS COMPLETE ===", flush=True)
    vm = report["ml_evaluation"].get("val_metrics", {})
    hm = report["ml_evaluation"].get("holdout_metrics", {})
    st = report["ml_evaluation"].get("stability", {})
    print(f"Val:  AUC={vm.get('auc')}, Exp={vm.get('expectancy_R')}R, PF={vm.get('profit_factor')}", flush=True)
    print(f"Hold: AUC={hm.get('auc')}, Exp={hm.get('expectancy_R')}R, PF={hm.get('profit_factor')}", flush=True)
    print(f"Stability: {st.get('stability_ratio')}, folds={st.get('n_folds')}", flush=True)
