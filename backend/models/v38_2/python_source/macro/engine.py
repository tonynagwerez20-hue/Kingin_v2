"""Macro / news intelligence engine.

Replaces the V37 "actual>forecast => bearish gold" heuristic with a
quantitative event model:

  raw surprise       = actual - forecast
  surprise_pct       = (actual - forecast) / max(|previous|, |forecast|, eps)
  normalized_surprise= surprise_pct clipped [-1,1]
  historical z-score = (surprise - mean(surprise_history)) / std(surprise_history)

  shock_type         = classify(category, sign & magnitude of surprise)
  expected_gold      = event_direction_map[category][shock_type][directionality]

  observed reaction  = measured FROM PRICE after release:
                       return, ATR-normalized return, MFE, MAE, vol expansion,
                       directional agreement — over multiple horizons.

This is NOT "CPI above forecast = bearish gold". The direction map encodes
per-category gold economics, but the *observed* reaction is always measured
from price and may contradict the expectation (reaction_conflict).

News modes (NEWS_* in config) change the engine's behaviour downstream; the
engine reports the relevant decision fields and the risk/execution layer acts
on them.

Calendar data must be supplied (CSV/Parquet). If absent, the engine reports
BLOCKED_BY_MISSING_CALENDAR_DATA and produces no events.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

import numpy as np
import pandas as pd

from ..config import V38Config, NEWS_OFF, NEWS_FILTER_ONLY, NEWS_REACTIVE, \
    NEWS_DIRECTIONAL, NEWS_HYBRID
from ..bars import atr
from .objects import MacroEvent, CalendarImportResult, EVENT_CATEGORIES, \
    SHOCK_TYPES, GOLD_IMPLICATIONS

# Required external calendar schema (documented for the user to supply).
CALENDAR_COLUMNS = [
    "ts", "country", "currency", "event_name", "category", "importance",
    "actual", "forecast", "previous", "revised_previous", "unit", "directionality",
]


# Category -> default gold implication by shock type.
# directionality "direct"  : higher actual => the implication sign applies.
# directionality "inverse": higher actual => implication flips.
GOLD_DIRECTION_MAP: Dict[str, Dict[str, str]] = {
    # inflation above forecast => inflationary shock => gold up (safe-haven + real-rates down)
    "inflation":      {"inflationary": "bullish", "neutral": "neutral", "deflationary": "bearish"},
    # strong payrolls/employment => USD up, rates up => gold down (labor shock)
    "employment":     {"labor_strong": "bearish", "neutral": "neutral", "labor_weak": "bullish"},
    "payrolls":       {"labor_strong": "bearish", "neutral": "neutral", "labor_weak": "bullish"},
    "unemployment":   {"labor_strong": "bearish", "neutral": "neutral", "labor_weak": "bullish"},
    "wages":          {"labor_strong": "bearish", "neutral": "neutral", "labor_weak": "bullish"},
    # hawkish central bank / rate hike => real rates up => gold down
    "central_bank":   {"hawkish": "bearish", "neutral": "neutral", "dovish": "bullish"},
    "interest_rate":  {"hawkish": "bearish", "neutral": "neutral", "dovish": "bullish"},
    "cb_communication":{"hawkish": "bearish", "neutral": "neutral", "dovish": "bullish"},
    # strong GDP/growth => USD up, risk on => gold down
    "gdp":            {"growth_strong": "bearish", "neutral": "neutral", "growth_weak": "bullish"},
    "retail_sales":    {"growth_strong": "bearish", "neutral": "neutral", "growth_weak": "bullish"},
    "manufacturing":   {"growth_strong": "bearish", "neutral": "neutral", "growth_weak": "bullish"},
    "services":        {"growth_strong": "bearish", "neutral": "neutral", "growth_weak": "bullish"},
    "consumer_confidence": {"growth_strong": "bearish", "neutral": "neutral", "growth_weak": "bullish"},
    "ppi":            {"inflationary": "bullish", "neutral": "neutral", "deflationary": "bearish"},
    # treasury yields up => real rates up => gold down
    "treasury_yield": {"yield_up": "bearish", "neutral": "neutral", "yield_down": "bullish"},
    "other":          {"neutral": "neutral"},
}


class MacroEngine:
    def __init__(self, cfg: V38Config):
        self.cfg = cfg
        self.events: List[MacroEvent] = []
        self.calendar_loaded = False
        self.blocked_reason = "BLOCKED_BY_MISSING_CALENDAR_DATA"

    def macro_feature_state(self) -> dict:
        """Return the PIT-safe macro feature state for a candidate setup.

        Phase E: forecast-dependent features (surprise, surprise_zscore,
        macro_direction) are ABSENT (NaN + macro_data_blocked=True) when
        genuine PIT forecast consensus is unavailable. They MUST NOT be
        substituted with current/revised forecasts and MUST NOT silently
        become 0. Features that need only event timing (importance,
        time_since_event, observed_reaction_state) are PIT-safe in principle
        but remain DATA_BLOCKED while the calendar is absent.
        """
        blocked = not self.calendar_loaded
        return {
            "macro_data_blocked": blocked,
            "blocked_reason": self.blocked_reason,
            # forecast-dependent — PIT_BLOCKED_NO_SOURCE without a PIT calendar
            "surprise": None if blocked else "computed_from_pit_actual_minus_pit_forecast",
            "surprise_pct": None if blocked else "computed_from_pit_surprise_over_pit_previous_base",
            "surprise_zscore": None if blocked else "computed_from_>=30_prior_pit_surprises",
            "macro_direction": None if blocked else "computed_from_pit_surprise",
            # PIT-safe-in-principle (no forecast needed) but data-blocked
            "latest_event_importance": None if blocked else "from_calendar_importance_label",
            "time_since_event": None if blocked else "entry_ts_minus_event_ts",
            "observed_reaction_state": None if blocked else "price_measured_leakage_safe",
            "forecast_pit_source": "absent (no free PIT consensus source; "
                                   "Trading Economics PIT not authorized)",
        }

    # ----------------------------------------------------- calendar loading
    def load_calendar(self, path: str) -> CalendarImportResult:
        try:
            df = pd.read_csv(path) if str(path).endswith(".csv") else pd.read_parquet(path)
        except FileNotFoundError:
            self.blocked_reason = "BLOCKED_BY_MISSING_CALENDAR_DATA"
            return CalendarImportResult(0, 0, self.blocked_reason)
        except Exception as e:
            self.blocked_reason = f"BLOCKED_BY_CALENDAR_PARSE_ERROR: {e}"
            return CalendarImportResult(0, 0, self.blocked_reason)

        missing = [c for c in CALENDAR_COLUMNS if c not in df.columns]
        if missing:
            self.blocked_reason = f"BLOCKED_BY_CALENDAR_SCHEMA: missing {missing}"
            return CalendarImportResult(0, len(df), self.blocked_reason)

        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
        events: List[MacroEvent] = []
        for i, row in df.iterrows():
            cat = str(row.get("category", "other")).strip().lower()
            if cat not in EVENT_CATEGORIES:
                cat = "other"
            events.append(MacroEvent(
                event_id=f"ME{i}",
                ts=pd.Timestamp(row["ts"]),
                country=str(row.get("country", "")),
                currency=str(row.get("currency", "")),
                event_name=str(row.get("event_name", "")),
                category=cat,
                importance=int(row.get("importance", 1) or 1),
                actual=_to_float(row.get("actual")),
                forecast=_to_float(row.get("forecast")),
                previous=_to_float(row.get("previous")),
                revised_previous=_to_float(row.get("revised_previous")),
                unit=str(row.get("unit", "")),
                directionality=str(row.get("directionality", "direct")).lower(),
            ))
        self.events = events
        self.calendar_loaded = True
        self.blocked_reason = ""
        return CalendarImportResult(n_loaded=len(events), n_rejected=0)

    # --------------------------------------------------- surprise & direction
    def compute_surprises(self) -> None:
        """Compute raw surprise, surprise %, normalized surprise, z-score,
        shock type, and expected gold implication. Requires actual+forecast."""
        # build per-(currency,category) surprise history for z-scores
        hist: Dict[Tuple[str, str], List[float]] = {}
        for e in self.events:
            e.surprise = _surprise(e.actual, e.forecast)
            e.surprise_pct = _surprise_pct(e)
            e.normalized_surprise = (
                max(-1.0, min(1.0, e.surprise_pct))) if e.surprise_pct is not None else None
            key = (e.currency, e.category)
            e.shock_type = _shock_type(e)
            e.expected_gold_implication = _gold_implication(e)
            if e.surprise is not None and not np.isnan(e.surprise):
                hist.setdefault(key, []).append(e.surprise)

        # second pass for z-scores (using only prior history to avoid leakage)
        running: Dict[Tuple[str, str], List[float]] = {}
        for e in self.events:
            key = (e.currency, e.category)
            arr = np.array(running.get(key, []), dtype=float)
            if e.surprise is not None and not np.isnan(e.surprise) and len(arr) >= 30:
                mu, sd = float(arr.mean()), float(arr.std(ddof=0))
                if sd > 0:
                    e.historical_surprise_z = float((e.surprise - mu) / sd)
            if e.surprise is not None and not np.isnan(e.surprise):
                running.setdefault(key, []).append(e.surprise)

    # ------------------------------------------------------ gold reaction
    def measure_reactions(self, price_df: pd.DataFrame) -> None:
        """Measure the actual gold reaction from price bars after each event.

        Requires the price series covering the event timestamps. Reactions
        are computed only if the price data contains bars strictly after the
        event. No look-ahead: reaction fields are only usable for a setup whose
        entry is after the reaction horizon completes.
        """
        if not self.events:
            return
        ts_idx = price_df["ts"].values.astype("datetime64[ns]")
        highs = price_df["high"].to_numpy()
        lows = price_df["low"].to_numpy()
        closes = price_df["close"].to_numpy()
        atr_arr = atr(price_df, self.cfg.displacement_atr_period)
        prev_close = np.empty(len(price_df))
        prev_close[0] = closes[0]
        prev_close[1:] = closes[:-1]
        tr = np.maximum.reduce([
            highs - lows, np.abs(highs - prev_close), np.abs(lows - prev_close),
        ])
        atr_safe = np.where(np.isnan(atr_arr), tr, atr_arr)
        horizons = self.cfg.news_reaction_horizons

        for e in self.events:
            # find the first price bar at/after event ts
            i = int(np.searchsorted(ts_idx, np.datetime64(e.ts.replace(tzinfo=None)), side="left"))
            if i <= 0 or i >= len(ts_idx):
                continue
            pre_close = float(closes[i - 1])
            pre_atr = float(atr_safe[i - 1]) if atr_safe[i - 1] > 0 else 1.0
            e.vol_before_atr = pre_atr
            reaction: Dict[str, float] = {}
            for h in horizons:
                j = min(len(closes) - 1, i + h)
                if j <= i:
                    continue
                ret = float(closes[j] - pre_close)
                ret_atr = ret / pre_atr if pre_atr > 0 else 0.0
                seg_high = float(np.max(highs[i:j + 1]))
                seg_low = float(np.min(lows[i:j + 1]))
                mfe = max(0.0, seg_high - pre_close)
                mae = max(0.0, pre_close - seg_low)
                direction = "up" if ret > 0 else ("down" if ret < 0 else "flat")
                reaction[f"ret_{h}"] = ret
                reaction[f"ret_atr_{h}"] = float(ret_atr)
                reaction[f"mfe_{h}"] = float(mfe)
                reaction[f"mae_{h}"] = float(mae)
                reaction[f"dir_{h}"] = direction
            # vol expansion: post-ATR vs pre-ATR over the first horizon that exists
            if horizons:
                h0 = horizons[0]
                j = min(len(closes) - 1, i + h0)
                if j > i:
                    post_atr = float(atr_safe[j]) if atr_safe[j] > 0 else pre_atr
                    reaction["vol_expansion"] = float(post_atr / pre_atr) if pre_atr > 0 else 1.0
            # directional agreement with expectation
            if horizons and e.expected_gold_implication in ("bullish", "bearish"):
                h0 = horizons[0]
                d = reaction.get(f"dir_{h0}", "flat")
                exp_dir = "up" if e.expected_gold_implication == "bullish" else "down"
                reaction["directional_agreement"] = 1.0 if d == exp_dir else (
                    -1.0 if d != "flat" else 0.0)
            else:
                reaction["directional_agreement"] = 0.0
            reaction["reaction_conflict"] = reaction.get("directional_agreement", 0.0) < 0.0
            e.reaction = reaction
            e.reaction_horizons = [h for h in horizons if i + h < len(closes)]
            e.vol_after_atr = reaction.get("vol_expansion", 1.0)
            e.state = "measured"

    # ------------------------------------------------------- query interface
    def active_events_at(self, ts: pd.Timestamp, lookback_min: int = 60
                         ) -> List[MacroEvent]:
        """Events released within `lookback_min` before `ts` (their reaction
        may still be forming). Leakage-safe: only events with ts <= entry."""
        if not self.events:
            return []
        lo = ts - pd.Timedelta(minutes=lookback_min)
        return [e for e in self.events if lo <= e.ts <= ts]

    def upcoming_events_at(self, ts: pd.Timestamp, ahead_min: int = 60
                           ) -> List[MacroEvent]:
        """Events scheduled within `ahead_min` after `ts` (event risk)."""
        if not self.events:
            return []
        hi = ts + pd.Timedelta(minutes=ahead_min)
        return [e for e in self.events if ts < e.ts <= hi]

    # ----------------------------------------------------- mode behaviour
    def decision(self, ts: pd.Timestamp, smc_direction: Optional[str],
                 cfg: V38Config) -> dict:
        """Return the news-mode-driven decision envelope for a setup at `ts`.

        The mode genuinely changes the output fields consumed by risk/execution.
        """
        mode = cfg.news_mode
        result = {"mode": mode, "veto": False, "confidence_adjustment": 0.0,
                  "reason": "", "event_risk": False, "alignment": 0.0,
                  "calendar_blocked": (not self.calendar_loaded)}
        if mode == NEWS_OFF:
            result["reason"] = "news engine off"
            return result
        # active = recently released (reaction observable before entry)
        active = self.active_events_at(ts, lookback_min=60)
        upcoming = self.upcoming_events_at(ts, ahead_min=60)
        high_imp = any(e.importance >= 3 for e in upcoming) or \
                   any(e.importance >= 3 for e in active)
        result["event_risk"] = high_imp

        if mode == NEWS_FILTER_ONLY:
            # veto high-impact upcoming events; never trade merely on headline
            if high_imp and upcoming:
                result["veto"] = True
                result["reason"] = "veto: high-impact event imminent"
            return result

        if mode == NEWS_REACTIVE:
            # trade only if there was a real reaction aligned with SMC
            if not active:
                result["reason"] = "no recent reactive event"
                return result
            e = max(active, key=lambda x: x.importance)
            agree = (e.reaction or {}).get("directional_agreement", 0.0)
            if e.reaction and agree > 0 and smc_direction == e.expected_gold_implication:
                result["alignment"] = agree
                result["confidence_adjustment"] = 0.05 * agree
            else:
                result["veto"] = True
                result["reason"] = "reaction not aligned with SMC"
            return result

        if mode == NEWS_DIRECTIONAL:
            if not active and not upcoming:
                result["reason"] = "no directional event"
                return result
            e = max((active + upcoming), key=lambda x: x.importance)
            result["alignment"] = 1.0 if e.expected_gold_implication == smc_direction else -1.0
            if e.expected_gold_implication != smc_direction and smc_direction is not None:
                result["veto"] = True
                result["reason"] = "directional conflict with macro"
            return result

        if mode == NEWS_HYBRID:
            e = max((active + upcoming), key=lambda x: x.importance, default=None)
            if e is None:
                result["reason"] = "no event for hybrid mode"
                return result
            agree = (e.reaction or {}).get("directional_agreement", 0.0)
            smc_aligned = (smc_direction == e.expected_gold_implication)
            result["alignment"] = (agree + (1.0 if smc_aligned else 0.0)) / 2.0
            if not (smc_aligned or agree > 0):
                result["veto"] = True
                result["reason"] = "hybrid: macro + reaction + SMC not aligned"
            return result
        return result


# ----------------------------------------------------------------- helpers
def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _surprise(actual, forecast) -> Optional[float]:
    if actual is None or forecast is None:
        return None
    return float(actual - forecast)


def _surprise_pct(e: MacroEvent) -> Optional[float]:
    if e.surprise is None:
        return None
    base = max(abs(e.previous or 0.0), abs(e.forecast or 0.0), 1e-9)
    return float(e.surprise / base)


def _shock_type(e: MacroEvent) -> str:
    """Classify the surprise into a shock type per category."""
    s = e.surprise
    if s is None or np.isnan(s):
        return "neutral"
    pos = s > 0
    mag = abs(e.normalized_surprise or 0.0)
    if mag < 0.15:
        return "neutral"
    cat = e.category
    if cat in ("inflation", "ppi"):
        return "inflationary" if pos else "deflationary"
    if cat in ("employment", "payrolls", "unemployment", "wages"):
        return "labor_strong" if pos else "labor_weak"
    if cat in ("central_bank", "interest_rate", "cb_communication"):
        return "hawkish" if pos else "dovish"
    if cat in ("gdp", "retail_sales", "manufacturing", "services",
              "consumer_confidence"):
        return "growth_strong" if pos else "growth_weak"
    if cat == "treasury_yield":
        return "yield_up" if pos else "yield_down"
    return "risk_safe_haven"


def _gold_implication(e: MacroEvent) -> str:
    cat_map = GOLD_DIRECTION_MAP.get(e.category, GOLD_DIRECTION_MAP["other"])
    st = e.shock_type
    imp = cat_map.get(st, "neutral")
    if e.directionality == "inverse" and imp != "neutral":
        imp = "bearish" if imp == "bullish" else ("bullish" if imp == "bearish" else "neutral")
    return imp
