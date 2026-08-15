"""V38 feature engine — computes the canonical feature vector from a
leakage-safe MarketStructure snapshot.

The engine never reads the future: it consumes `MarketStructure.snapshot(bar)`
plus the bar's OHLC/ATR. Every helper uses only objects whose
`confirmation_bar <= bar`.

Missing-value policy: structural features return 0/neutral when no object is
confirmed; macro features return 0 when no calendar is loaded or no event is
present. This is documented per-feature in the contract and reproduced exactly
in MQL5.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import V38Config
from ..bars import atr, session_of
from ..structure.orchestrator import MarketStructure
from ..macro.engine import MacroEngine
from .contract import FEATURE_NAMES, N_FEATURES, FEATURE_CONTRACT_VERSION


NAN_SENTINEL = 0.0  # missing-value fill used identically in Python and MQL5


class FeatureEngine:
    def __init__(self, cfg: V38Config, ms: MarketStructure,
                 macro: Optional[MacroEngine] = None,
                 ltf: str = "H1", htf: str = "H4"):
        self.cfg = cfg
        self.ms = ms
        self.macro = macro
        self.ltf = ltf
        self.htf = htf
        self._atr_cache: Dict[str, np.ndarray] = {}
        # Precompute the mapping from each LTF bar index to the corresponding
        # HTF bar index (last HTF bar with open-time <= LTF bar open-time).
        # This is the leakage-correct cross-TF alignment, done once.
        self._htf_idx_for_ltf = self._build_cross_tf_index()

    def _build_cross_tf_index(self) -> np.ndarray:
        import warnings
        if self.htf not in self.ms.tfs:
            return np.array([], dtype=np.int64)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            ltf_ts = self.ms.tfs[self.ltf].df["ts"].to_numpy().astype("datetime64[ns]")
            htf_ts = self.ms.tfs[self.htf].df["ts"].to_numpy().astype("datetime64[ns]")
        idx = np.searchsorted(htf_ts, ltf_ts, side="right") - 1
        idx = np.clip(idx, 0, len(htf_ts) - 1)
        return idx.astype(np.int64)

    # ----------------------------------------------------------- public
    def vector(self, bar_index: int, direction: str = "bullish") -> np.ndarray:
        """Return the feature vector (N_FEATURES,) for the LTF bar."""
        v = np.zeros(N_FEATURES, dtype=np.float32)
        snap = self.ms.snapshot(self.ltf, bar_index)
        if self.htf in self.ms.tfs and bar_index < len(self._htf_idx_for_ltf):
            htf_snap = self.ms.snapshot(self.htf, int(self._htf_idx_for_ltf[bar_index]))
        else:
            htf_snap = None
        df_l = self.ms.tfs[self.ltf].df
        atr_arr_l = self._atr_series(self.ltf)

        reg_enc = {"bearish": 0.0, "neutral": 1.0, "bullish": 2.0}
        dir_enc = {"bearish": -1.0, "neutral": 0.0, "bullish": 1.0}

        # ---------------- STRUCTURE ----------------
        v[0] = reg_enc.get(htf_snap["regime"] if htf_snap else "neutral", 1.0)
        v[1] = reg_enc.get(snap["regime"], 1.0)
        v[2] = self._bos_recent(snap)
        v[3] = self._choch_recent(snap)
        v[4] = self._last_event_dir(snap, dir_enc)
        v[5] = self._last_event_disp_atr(snap)
        v[6] = self._last_event_age(snap, bar_index)
        v[7] = self._protected_high(snap)
        v[8] = self._protected_low(snap)
        v[9] = self._multi_leg_aligned(htf_snap, snap)
        v[10] = self._leg_extension_atr(snap, atr_arr_l, bar_index)
        v[11] = self._structure_strength(snap)

        # ---------------- LIQUIDITY ----------------
        price = float(df_l["close"].to_numpy()[bar_index])
        a = float(atr_arr_l[bar_index]) if not np.isnan(atr_arr_l[bar_index]) else 1.0
        a = a if a > 0 else 1.0
        dist, side = self._nearest_liq(snap, price, a)
        v[12] = dist
        v[13] = side
        v[14] = self._liquidity_swept(snap, bar_index)
        v[15] = self._sweep_depth(snap)
        v[16] = self._post_sweep_reaction(snap)
        v[17] = self._eqh_eql_present(snap, bar_index)
        v[18] = self._inducement_present(snap, bar_index)

        # ---------------- ORDER BLOCK ----------------
        ob = self._nearest_valid_ob(snap, price, a)
        v[19] = 1.0 if ob is not None else 0.0
        v[20] = dir_enc.get(ob.direction, 0.0) if ob else 0.0
        v[21] = float(ob.quality) if ob else 0.0
        v[22] = self._ob_distance(ob, price, a)
        v[23] = self._ob_age(ob, bar_index)
        v[24] = float(ob.mitigation_count) if ob else 0.0
        v[25] = self._ob_freshness_enc(ob)
        v[26] = float(ob.deepest_penetration_pct) if ob else 0.0

        # ---------------- FVG ----------------
        fvg = self._nearest_open_fvg(snap, price, a)
        v[27] = 1.0 if fvg is not None else 0.0
        v[28] = dir_enc.get(fvg.direction, 0.0) if fvg else 0.0
        v[29] = float(fvg.size_atr) if fvg else 0.0
        v[30] = self._fvg_age(fvg, bar_index)
        v[31] = float(fvg.fill_percentage) if fvg else 0.0
        v[32] = self._fvg_freshness_enc(fvg)

        # ---------------- PREMIUM / DISCOUNT ----------------
        pd_state = snap["pd"]
        if pd_state and pd_state.leg_id is not None:
            v[33] = float(pd_state.position)
            v[34] = {"discount": 0.0, "equilibrium": 1.0, "premium": 2.0,
                     "unknown": 1.0}.get(pd_state.premium_discount, 1.0)
            v[35] = float(pd_state.distance_from_eq)
            v[36] = self._pd_leg_span(pd_state, a)
        else:
            v[33] = 0.5
            v[34] = 1.0
            v[35] = 0.0
            v[36] = 0.0

        # ---------------- MARKET REGIME ----------------
        v[37] = float(a)
        v[38] = self._atr_pct(atr_arr_l, bar_index)
        v[39] = self._daily_range_pct(df_l, bar_index, a)
        v[40] = self._vol_regime(v[38])
        v[41] = float(df_l["spread"].to_numpy()[bar_index])

        # ---------------- SESSION ----------------
        ts = df_l["ts"].to_numpy()[bar_index]
        v[42] = self._session_enc(ts)
        v[43] = self._session_phase_enc(ts)

        # ---------------- MACRO / NEWS ----------------
        v[44] = self._event_present(ts)
        v[45] = self._event_importance(ts)
        v[46] = self._normalized_surprise(ts)
        v[47] = self._surprise_z(ts)
        v[48] = self._expected_gold_dir(ts, dir_enc)
        v[49] = self._observed_reaction(ts)

        # ---------------- SETUP GEOMETRY ----------------
        dir_sign = 1.0 if direction == "bullish" else (-1.0 if direction == "bearish" else 0.0)
        v[50] = dir_sign * reg_enc.get(htf_snap["regime"] if htf_snap else "neutral", 1.0) - 1.0 \
            if False else self._alignment(htf_snap, direction, reg_enc)
        v[50] = self._alignment(htf_snap, direction, reg_enc)
        v[51] = self._alignment(snap, direction, reg_enc)
        v[52] = self._dist_to_entry(ob, fvg, price, a)
        v[53] = self._sl_distance(direction, snap, price, a)
        v[54] = self._tp_distance(v[53])
        v[55] = self._available_rr(v[53], v[54])

        # sanitize NaN/inf
        v = np.nan_to_num(v, nan=NAN_SENTINEL, posinf=NAN_SENTINEL,
                          neginf=NAN_SENTINEL).astype(np.float32)
        return v

    # --------------------------------------------------- internal helpers
    def _atr_series(self, tf: str) -> np.ndarray:
        if tf in self._atr_cache:
            return self._atr_cache[tf]
        df = self.ms.tfs[tf].df
        a = atr(df, self.cfg.displacement_atr_period)
        # forward-fill the warmup NaN with TR-based fallback for robustness
        if np.isnan(a[0]):
            prev_close = np.empty(len(df))
            cl = df["close"].to_numpy()
            prev_close[0] = cl[0]
            prev_close[1:] = cl[:-1]
            tr = np.maximum.reduce([
                df["high"].to_numpy() - df["low"].to_numpy(),
                np.abs(df["high"].to_numpy() - prev_close),
                np.abs(df["low"].to_numpy() - prev_close),
            ])
            mask = np.isnan(a)
            a[mask] = tr[mask]
        self._atr_cache[tf] = a
        return a

    @staticmethod
    def _bos_recent(snap) -> float:
        evs = [e for e in snap["events"][-50:] if e.event_type == "BOS"]
        return float(len(evs))

    @staticmethod
    def _choch_recent(snap) -> float:
        evs = [e for e in snap["events"][-50:] if e.event_type == "CHOCH"]
        return float(len(evs))

    @staticmethod
    def _last_event_dir(snap, dir_enc) -> float:
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        if not evs:
            return 0.0
        return dir_enc.get(evs[-1].direction, 0.0)

    @staticmethod
    def _last_event_disp_atr(snap) -> float:
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        return float(evs[-1].displacement_atr) if evs else 0.0

    @staticmethod
    def _last_event_age(snap, bar_index) -> float:
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        if not evs:
            return -1.0
        return float(bar_index - evs[-1].confirmation_bar)

    @staticmethod
    def _protected_high(snap) -> float:
        prots = [p for p in snap["protected"] if p.kind == "high" and p.status == "active"]
        return float(prots[-1].price) if prots else NAN_SENTINEL

    @staticmethod
    def _protected_low(snap) -> float:
        prots = [p for p in snap["protected"] if p.kind == "low" and p.status == "active"]
        return float(prots[-1].price) if prots else NAN_SENTINEL

    @staticmethod
    def _multi_leg_aligned(htf_snap, snap) -> float:
        if not htf_snap:
            return 0.0
        a = htf_snap["regime"]
        b = snap["regime"]
        if a == b and a != "neutral":
            return 1.0
        return 0.0

    def _leg_extension_atr(self, snap, atr_arr, bar_index) -> float:
        legs = snap["legs"]
        if not legs:
            return 0.0
        leg = legs[-1]
        ext = abs(float(self.ms.tfs[self.ltf].df["close"].to_numpy()[bar_index]) - leg.start_price)
        a = float(atr_arr[bar_index]) if not np.isnan(atr_arr[bar_index]) else 1.0
        a = a if a > 0 else 1.0
        return float(ext / a)

    @staticmethod
    def _structure_strength(snap) -> float:
        evs = [e for e in snap["events"] if e.event_type in ("BOS", "CHOCH")]
        return float(min(1.0, evs[-1].quality)) if evs else 0.0

    # liquidity
    @staticmethod
    def _nearest_liq(snap, price, atr_v) -> Tuple[float, float]:
        pools = [p for p in snap["pools"] if not p.invalidated]
        if not pools:
            return 0.0, 0.0
        nearest = min(pools, key=lambda p: abs(p.price - price))
        d = abs(nearest.price - price) / (atr_v if atr_v > 0 else 1.0)
        side = 1.0 if nearest.price >= price else -1.0
        if nearest.type == "high" and nearest.price < price:
            side = -1.0
        if nearest.type == "low" and nearest.price > price:
            side = 1.0
        return float(d), float(side)

    @staticmethod
    def _liquidity_swept(snap, bar_index) -> float:
        swept = [p for p in snap["pools"] if p.swept
                 and p.sweep_bar is not None
                 and (bar_index - p.sweep_bar) <= 10
                 and (bar_index - p.sweep_bar) >= 0]
        return 1.0 if swept else 0.0

    @staticmethod
    def _sweep_depth(snap) -> float:
        swept = [p for p in snap["pools"] if p.swept]
        return float(swept[-1].sweep_depth_atr) if swept else 0.0

    @staticmethod
    def _post_sweep_reaction(snap) -> float:
        swept = [p for p in snap["pools"] if p.swept]
        return float(swept[-1].post_sweep_reaction_atr) if swept else 0.0

    @staticmethod
    def _eqh_eql_present(snap, bar_index) -> float:
        eqs = [e for e in snap["equals"]
               if (bar_index - e.confirmation_bar) <= 100
               and (bar_index - e.confirmation_bar) >= 0]
        return 1.0 if eqs else 0.0

    @staticmethod
    def _inducement_present(snap, bar_index) -> float:
        inds = [i for i in snap["inducements"]
                if (bar_index - i.confirmation_bar) <= 50
                and (bar_index - i.confirmation_bar) >= 0]
        return 1.0 if inds else 0.0

    # order block
    @staticmethod
    def _nearest_valid_ob(snap, price, atr_v):
        valid = [o for o in snap["order_blocks"]
                 if not o.invalidated and o.lifecycle in ("fresh", "touched", "partially_consumed")]
        if not valid:
            return None
        def dist(o):
            zone = o.upper - o.lower
            if price < o.lower:
                return o.lower - price
            if price > o.upper:
                return price - o.upper
            return 0.0
        return min(valid, key=dist)

    @staticmethod
    def _ob_distance(ob, price, atr_v) -> float:
        if ob is None:
            return 0.0
        if price < ob.lower:
            d = ob.lower - price
        elif price > ob.upper:
            d = price - ob.upper
        else:
            return 0.0
        return float(d / (atr_v if atr_v > 0 else 1.0))

    @staticmethod
    def _ob_age(ob, bar_index) -> float:
        if ob is None:
            return 0.0
        return float(bar_index - ob.confirmation_bar)

    @staticmethod
    def _ob_freshness_enc(ob) -> float:
        if ob is None:
            return 0.0
        return {"fresh": 1.0, "touched": 2.0, "stale": 3.0}.get(ob.freshness, 0.0)

    # FVG
    @staticmethod
    def _nearest_open_fvg(snap, price, atr_v):
        open_fvgs = [f for f in snap["fvgs"]
                     if f.lifecycle in ("open", "partially_filled")]
        if not open_fvgs:
            return None
        def dist(f):
            if price < f.lower:
                return f.lower - price
            if price > f.upper:
                return price - f.upper
            return 0.0
        return min(open_fvgs, key=dist)

    @staticmethod
    def _fvg_age(fvg, bar_index) -> float:
        if fvg is None:
            return 0.0
        return float(bar_index - fvg.confirmation_bar)

    @staticmethod
    def _fvg_freshness_enc(fvg) -> float:
        if fvg is None:
            return 0.0
        return {"open": 1.0, "partially_filled": 2.0,
                "fully_filled": 3.0}.get(fvg.lifecycle, 0.0)

    # premium/discount
    @staticmethod
    def _pd_leg_span(pd_state, atr_v) -> float:
        span = pd_state.leg_high - pd_state.leg_low
        return float(span / (atr_v if atr_v > 0 else 1.0))

    # market regime
    def _atr_pct(self, atr_arr, bar_index) -> float:
        lb = self.cfg.atr_percentile_lookback
        lo = max(0, bar_index - lb)
        window = atr_arr[lo:bar_index + 1]
        window = window[~np.isnan(window)]
        if len(window) == 0:
            return 0.5
        cur = atr_arr[bar_index]
        if np.isnan(cur):
            return 0.5
        pct = float(np.sum(window <= cur)) / len(window)
        return pct

    @staticmethod
    def _daily_range_pct(df, bar_index, atr_v) -> float:
        # current bar range vs ATR (proxy for daily-range pct on intraday TFs)
        h = float(df["high"].to_numpy()[bar_index])
        l = float(df["low"].to_numpy()[bar_index])
        r = h - l
        val = r / (atr_v if atr_v > 0 else 1.0)
        return float(max(0.0, min(1.0, val / 4.0)))  # normalize ~4 ATR/day

    def _vol_regime(self, atr_pct) -> float:
        if atr_pct * 100 < self.cfg.vol_regime_low_pct:
            return 0.0
        if atr_pct * 100 >= self.cfg.vol_regime_high_pct:
            return 2.0
        return 1.0

    # session
    def _session_enc(self, ts) -> float:
        return float({"asian": 0, "london": 1, "overlap": 2,
                      "ny": 3, "off": 4}.get(session_of(pd.Timestamp(ts), self.cfg), 4))

    def _session_phase_enc(self, ts) -> float:
        name = session_of(pd.Timestamp(ts), self.cfg)
        start, end = self.cfg.session_defs.get(name, (0, 24))
        hour = pd.Timestamp(ts).hour
        if start == end:
            return 0.0
        frac = (hour - start) / (end - start)
        if frac < 0.33:
            return 0.0
        if frac < 0.66:
            return 1.0
        return 2.0

    # macro
    def _event_present(self, ts) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        t = pd.Timestamp(ts)
        active = self.macro.active_events_at(t, 60)
        upcoming = self.macro.upcoming_events_at(t, 60)
        high = any(e.importance >= 2 for e in active + upcoming)
        return 1.0 if high else 0.0

    def _event_importance(self, ts) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        t = pd.Timestamp(ts)
        evs = self.macro.active_events_at(t, 60) + self.macro.upcoming_events_at(t, 60)
        return float(max((e.importance for e in evs), default=0))

    def _normalized_surprise(self, ts) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        evs = self.macro.active_events_at(pd.Timestamp(ts), 60)
        for e in reversed(evs):
            if e.normalized_surprise is not None:
                return float(e.normalized_surprise)
        return 0.0

    def _surprise_z(self, ts) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        evs = self.macro.active_events_at(pd.Timestamp(ts), 60)
        for e in reversed(evs):
            if e.historical_surprise_z is not None:
                return float(e.historical_surprise_z)
        return 0.0

    def _expected_gold_dir(self, ts, dir_enc) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        evs = self.macro.active_events_at(pd.Timestamp(ts), 60)
        for e in reversed(evs):
            return dir_enc.get(e.expected_gold_implication, 0.0)
        return 0.0

    def _observed_reaction(self, ts) -> float:
        if self.macro is None or not self.macro.calendar_loaded:
            return 0.0
        evs = self.macro.active_events_at(pd.Timestamp(ts), 60)
        for e in reversed(evs):
            if e.reaction and "ret_atr_5" in e.reaction:
                return float(e.reaction["ret_atr_5"])
        return 0.0

    # setup geometry
    @staticmethod
    def _alignment(snap, direction, reg_enc) -> float:
        if snap is None:
            return 0.0
        reg = snap["regime"]
        if direction == reg:
            return 1.0
        if direction == "neutral" or reg == "neutral":
            return 0.0
        return -1.0

    @staticmethod
    def _dist_to_entry(ob, fvg, price, atr_v) -> float:
        target = None
        if ob is not None:
            target = ob.lower if price > ob.upper else (ob.upper if price < ob.lower else price)
        elif fvg is not None:
            target = fvg.lower if price > fvg.upper else (fvg.upper if price < fvg.lower else price)
        if target is None:
            return 0.0
        return float(abs(target - price) / (atr_v if atr_v > 0 else 1.0))

    @staticmethod
    def _sl_distance(direction, snap, price, atr_v) -> float:
        # structural SL = beyond the nearest protected level / swing extreme
        prots_h = [p for p in snap["protected"] if p.kind == "high" and p.status == "active"]
        prots_l = [p for p in snap["protected"] if p.kind == "low" and p.status == "active"]
        if direction == "bullish":
            ref = min([p.price for p in prots_l], default=price)
            d = price - ref
        else:
            ref = max([p.price for p in prots_h], default=price)
            d = ref - price
        d = max(0.0, d)
        return float(d / (atr_v if atr_v > 0 else 1.0))

    @staticmethod
    def _tp_distance(sl_distance) -> float:
        return float(sl_distance * 2.0)  # 2R target by default

    @staticmethod
    def _available_rr(sl_distance, tp_distance) -> float:
        return float(tp_distance / sl_distance) if sl_distance > 0 else 0.0


def features_as_dict(vec: np.ndarray) -> Dict[str, float]:
    return {name: float(vec[i]) for i, name in enumerate(FEATURE_NAMES)}
