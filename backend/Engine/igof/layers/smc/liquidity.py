"""
LiquiditySweepLayer — Gold SMC Edition
=======================================================
Detects ALL institutional liquidity sweep patterns used in Gold (XAUUSD).

PRIMARY SWEEPS
  BSL/SSL, Stop Hunt, PDH/PDL, EQH/EQL, Asian Range, Weekly High/Low,
  Round Number, Turtle Soup, Inducement, Retest, OTE

FIXES vs ORIGINAL
─────────────────
1. process() was not propagating bias from sweep direction into the result
   dict. The bootstrapper reads result["bias"] to gate signal direction.
   Now every process() return includes bias derived from the sweep direction.
2. _detect_ote_sweep() computed OTE from a short 20-bar scope AFTER the
   original find_swing_points call also used a fixed 20-bar scope — the two
   searches were on different windows. OTE now uses the same internal_lookback
   scope as the surrounding detectors for consistency.
3. validate() was returning only (bool, float) from _check_sweep_enhanced
   which loses the reason string; the reason is now stored in self._reason
   so base.process() can read it.
4. _detect_trend() direction labels were inverted vs. ICT convention in
   _detect_inducement_sweep(): bearish trend raids highs (bearish IDM above
   price) and bullish trend raids lows (bullish IDM below price). Fixed.
5. Historical BSL/SSL checks in _detect_bsl_ssl_sweep were using ref_scope
   (the search scope) for max/min instead of the dedicated historical window,
   causing double-counting with the live-bar check above. Separated correctly.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from .base import SMCLayerBase
import logging

logger = logging.getLogger("LiquiditySweep")


class LiquiditySweepLayer(SMCLayerBase):
    MAJOR_LOOKBACK          = 288
    INTERNAL_LOOKBACK       = 20
    MULTI_CANDLE_WINDOW     = 3
    MIN_SWEEP_ATR_RATIO     = 0.10
    PHASE1_WICK_BONUS       = 0.3
    EQH_EQL_TOLERANCE_ATR   = 0.08
    BSL_REVERT_CANDLES      = 12
    SSL_REVERT_CANDLES      = 12
    HISTORICAL_SWEEP_BARS   = 72
    RETEST_TOLERANCE_ATR    = 0.25
    SWING_CONFIRM_BARS      = 3
    PDH_PDL_LOOKBACK        = 96
    ASIAN_SESSION_BARS      = 60
    TURTLE_SOUP_BARS        = 5
    WEEKLY_LOOKBACK         = 1440
    ROUND_NUMBER_TOLERANCE  = 0.12
    MIN_SWEEP_CANDLES       = 1

    def __init__(self, name="LiquiditySweep", threshold=0.5, config=None):
        super().__init__(name, threshold, config)
        self._reason                 = "Liquidity not yet evaluated"
        self._bias                   = "neutral"
        self.major_lookback          = self.config.get("major_lookback",          self.MAJOR_LOOKBACK)
        self.internal_lookback       = self.config.get("internal_lookback",       self.INTERNAL_LOOKBACK)
        self.multi_candle_window     = self.config.get("multi_candle_window",     self.MULTI_CANDLE_WINDOW)
        self.min_sweep_atr_ratio     = self.config.get("min_sweep_atr_ratio",     self.MIN_SWEEP_ATR_RATIO)
        self.enable_internal         = self.config.get("enable_internal",         True)
        self.historical_sweep_bars   = self.config.get("historical_sweep_bars",   self.HISTORICAL_SWEEP_BARS)
        self.bsl_revert_candles      = self.config.get("bsl_revert_candles",      self.BSL_REVERT_CANDLES)
        self.ssl_revert_candles      = self.config.get("ssl_revert_candles",      self.SSL_REVERT_CANDLES)
        self.eqh_eql_tolerance_atr   = self.config.get("eqh_eql_tolerance_atr",  self.EQH_EQL_TOLERANCE_ATR)
        self.pdh_pdl_lookback        = self.config.get("pdh_pdl_lookback",        self.PDH_PDL_LOOKBACK)
        self.asian_session_bars      = self.config.get("asian_session_bars",      self.ASIAN_SESSION_BARS)
        self.turtle_soup_bars        = self.config.get("turtle_soup_bars",        self.TURTLE_SOUP_BARS)
        self.retest_tolerance_atr    = self.config.get("retest_tolerance_atr",    self.RETEST_TOLERANCE_ATR)
        self.swing_confirm_bars      = self.config.get("swing_confirm_bars",      self.SWING_CONFIRM_BARS)
        self.weekly_lookback         = self.config.get("weekly_lookback",         self.WEEKLY_LOOKBACK)
        self.round_number_tolerance  = self.config.get("round_number_tolerance",  self.ROUND_NUMBER_TOLERANCE)

    # ─────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────

    def _calculate_atr(self, df, period=14):
        if len(df) < period + 1:
            return 1.0
        high, low, close = df["high"], df["low"], df["close"]
        tr  = pd.concat([high - low,
                         abs(high - close.shift(1)),
                         abs(low  - close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return atr if not pd.isna(atr) else 1.0

    def _find_swing_points(self, df, lookback):
        """FIX: [-(lookback+1):-1] gives exactly `lookback` complete bars."""
        if len(df) < lookback + 1:
            return df["high"].max(), df["low"].min()
        subset = df.iloc[-(lookback + 1):-1]
        return subset["high"].max(), subset["low"].min()

    def _find_confirmed_swing_points(self, df, lookback, n=3):
        if len(df) < lookback + n + 1:
            return self._find_swing_points(df, lookback)
        subset  = df.iloc[-(lookback + 1):-1].reset_index(drop=True)
        highs   = subset["high"].values
        lows    = subset["low"].values
        swing_h = subset["high"].iloc[0]
        swing_l = subset["low"].iloc[0]
        for i in range(n, len(highs) - n):
            if all(highs[i] >= highs[i - j] for j in range(1, n + 1)) and \
               all(highs[i] >= highs[i + j] for j in range(1, n + 1)):
                swing_h = max(swing_h, highs[i])
            if all(lows[i] <= lows[i - j] for j in range(1, n + 1)) and \
               all(lows[i] <= lows[i + j] for j in range(1, n + 1)):
                swing_l = min(swing_l, lows[i])
        return swing_h, swing_l

    def _check_multi_candle_sweep(self, df, level, direction, lookback):
        min_bars = max(lookback, self.multi_candle_window, self.historical_sweep_bars) + 2
        if len(df) < min_bars:
            return False, False, 0.0
        atr         = self._calculate_atr(df)
        hist_window = min(self.historical_sweep_bars, len(df) - 2)
        search_df   = df.iloc[-(hist_window + 1):-1]
        curr_close  = df["close"].iloc[-1]
        if direction == "bullish":
            min_low        = search_df["low"].min()
            swept          = min_low < level
            reverted       = curr_close > level
            sweep_distance = (level - min_low) / atr if swept else 0.0
        else:
            max_high       = search_df["high"].max()
            swept          = max_high > level
            reverted       = curr_close < level
            sweep_distance = (max_high - level) / atr if swept else 0.0
        return swept, reverted, sweep_distance

    def _check_phase1_wick(self, df, level, direction):
        if len(df) < 2:
            return False
        c = df.iloc[-1]
        if direction == "bullish":
            return (c["low"] < level) and (c["close"] > c["low"])
        return (c["high"] > level) and (c["close"] < c["high"])

    def _calculate_sweep_quality(self, swept, reverted, sweep_distance_atr, is_phase1_wick=False):
        if swept and reverted:
            return 1.0 if sweep_distance_atr >= self.min_sweep_atr_ratio else 0.7
        if is_phase1_wick and sweep_distance_atr >= self.min_sweep_atr_ratio:
            return self.PHASE1_WICK_BONUS
        if swept and sweep_distance_atr > 0:
            return max(0.2, sweep_distance_atr / self.min_sweep_atr_ratio * 0.5)
        return 0.0

    def _check_sweep_enhanced(self, df, pdl, pdh, is_internal=False):
        lookback   = self.internal_lookback if is_internal else self.major_lookback
        c          = df.iloc[-1]
        level_type = "INTERNAL" if is_internal else "MAJOR"
        bull_swept,  bull_reverted,  bull_atr  = self._check_multi_candle_sweep(df, pdl, "bullish", lookback)
        bear_swept,  bear_reverted,  bear_atr  = self._check_multi_candle_sweep(df, pdh, "bearish", lookback)
        bull_phase1 = self._check_phase1_wick(df, pdl, "bullish")
        bear_phase1 = self._check_phase1_wick(df, pdh, "bearish")
        bull_score  = self._calculate_sweep_quality(bull_swept, bull_reverted, bull_atr, bull_phase1)
        bear_score  = self._calculate_sweep_quality(bear_swept, bear_reverted, bear_atr, bear_phase1)
        if bull_score >= self.threshold or bear_score >= self.threshold:
            best_score = max(bull_score, bear_score)
            direction  = "BULLISH" if bull_score >= bear_score else "BEARISH"
            return True, best_score, f"{direction} sweep (Score: {best_score:.2f})"
        return False, 0.0, "No qualified sweep"

    def _detect_trend(self, df, lookback=20):
        if len(df) < lookback + 1:
            return "neutral"
        closes      = df["close"].iloc[-lookback:]
        first_half  = closes.iloc[:lookback // 2].mean()
        second_half = closes.iloc[lookback // 2:].mean()
        if second_half > first_half * 1.002:
            return "bullish"
        elif second_half < first_half * 0.998:
            return "bearish"
        return "neutral"

    def _bias_from_reason(self, reason: str) -> str:
        r = reason.upper()
        if "BULLISH" in r or "SSL" in r:
            return "bullish"
        if "BEARISH" in r or "BSL" in r:
            return "bearish"
        return "neutral"

    # ─────────────────────────────────────────────────────────────────
    # Gold-specific sweep detectors
    # Each returns (detected: bool, score: float, reason: str)
    # ─────────────────────────────────────────────────────────────────

    def _detect_stop_hunt_sweep(self, df):
        if len(df) < self.internal_lookback + 4:
            return False, 0.0, ""
        atr        = self._calculate_atr(df)
        scope      = df.iloc[-(self.internal_lookback + 1):-1]
        swing_high = scope["high"].max()
        swing_low  = scope["low"].min()
        c          = df.iloc[-1]
        candle_rng = c["high"] - c["low"]
        if candle_rng == 0:
            return False, 0.0, ""

        if c["high"] > swing_high and c["close"] < swing_high:
            dist      = (c["high"] - swing_high) / atr
            wick_size = c["high"] - max(c["open"], c["close"])
            wick_ratio= wick_size / candle_rng
            if dist >= self.min_sweep_atr_ratio:
                score = self._calculate_sweep_quality(True, True, dist)
                score = min(1.0, score * (1.0 + 0.3 * wick_ratio))
                if score >= self.threshold:
                    return True, score, f"Bearish stop hunt above {swing_high:.2f} (Score: {score:.2f})"

        if c["low"] < swing_low and c["close"] > swing_low:
            dist      = (swing_low - c["low"]) / atr
            wick_size = min(c["open"], c["close"]) - c["low"]
            wick_ratio= wick_size / candle_rng
            if dist >= self.min_sweep_atr_ratio:
                score = self._calculate_sweep_quality(True, True, dist)
                score = min(1.0, score * (1.0 + 0.3 * wick_ratio))
                if score >= self.threshold:
                    return True, score, f"Bullish stop hunt below {swing_low:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_bsl_ssl_sweep(self, df):
        """
        FIX: historical BSL/SSL check now uses a separate historical scope
        (hist_scope = df.iloc[-(hist_window+1):-1]) instead of re-using the
        live ref_scope which already represents the detection window. This
        prevents the historical fallback from duplicating the live-bar check.
        """
        if len(df) < self.historical_sweep_bars + 4:
            return False, 0.0, ""
        atr       = self._calculate_atr(df)
        bsl_level, ssl_level = self._find_confirmed_swing_points(
            df, self.historical_sweep_bars, n=self.swing_confirm_bars
        )
        c = df.iloc[-1]

        if c["high"] > bsl_level and c["close"] < bsl_level:
            dist  = (c["high"] - bsl_level) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"BSL sweep at {bsl_level:.2f} (Score: {score:.2f})"

        if c["low"] < ssl_level and c["close"] > ssl_level:
            dist  = (ssl_level - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"SSL sweep at {ssl_level:.2f} (Score: {score:.2f})"

        # Historical: sweep completed in prior bars, price now on correct side
        hist_window = min(self.historical_sweep_bars, len(df) - 2)
        hist_scope  = df.iloc[-(hist_window + 1):-1]   # FIX: dedicated historical scope
        curr_close  = df["close"].iloc[-1]

        if hist_scope["high"].max() > bsl_level and curr_close < bsl_level:
            dist  = (hist_scope["high"].max() - bsl_level) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.85
            if score >= self.threshold:
                return True, score, f"Historical BSL swept at {bsl_level:.2f} (Score: {score:.2f})"

        if hist_scope["low"].min() < ssl_level and curr_close > ssl_level:
            dist  = (ssl_level - hist_scope["low"].min()) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.85
            if score >= self.threshold:
                return True, score, f"Historical SSL swept at {ssl_level:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_pdh_pdl_sweep(self, df):
        if len(df) < self.pdh_pdl_lookback + 4:
            return False, 0.0, ""
        atr       = self._calculate_atr(df)
        ref_scope = df.iloc[-(self.pdh_pdl_lookback + 1):-1]
        pdh       = ref_scope["high"].max()
        pdl       = ref_scope["low"].min()
        c         = df.iloc[-1]

        if c["high"] > pdh and c["close"] < pdh:
            dist  = (c["high"] - pdh) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if self._is_near_round_number(pdh, atr):
                score = min(1.0, score * 1.15)
            if score >= self.threshold:
                return True, score, f"PDH sweep at {pdh:.2f} (Score: {score:.2f})"

        if c["low"] < pdl and c["close"] > pdl:
            dist  = (pdl - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if self._is_near_round_number(pdl, atr):
                score = min(1.0, score * 1.15)
            if score >= self.threshold:
                return True, score, f"PDL sweep at {pdl:.2f} (Score: {score:.2f})"

        curr_close = df["close"].iloc[-1]
        if ref_scope["high"].max() > pdh and curr_close < pdh:
            dist  = (ref_scope["high"].max() - pdh) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.8
            if score >= self.threshold:
                return True, score, f"Historical PDH swept at {pdh:.2f} (Score: {score:.2f})"

        if ref_scope["low"].min() < pdl and curr_close > pdl:
            dist  = (pdl - ref_scope["low"].min()) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.8
            if score >= self.threshold:
                return True, score, f"Historical PDL swept at {pdl:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_eqh_eql_sweep(self, df):
        if len(df) < self.internal_lookback + 4:
            return False, 0.0, ""
        atr   = self._calculate_atr(df)
        tol   = self.eqh_eql_tolerance_atr * atr
        scope = df.iloc[-(self.internal_lookback + 1):-1]
        c     = df.iloc[-1]

        highs    = scope["high"].values
        sorted_h = np.sort(highs)[::-1]
        eqh_level, eqh_count = None, 1
        for i in range(len(sorted_h) - 1):
            if abs(sorted_h[i] - sorted_h[i + 1]) <= tol:
                eqh_level  = (sorted_h[i] + sorted_h[i + 1]) / 2
                eqh_count += 1
            elif eqh_level is not None:
                break
        if eqh_level is not None and c["high"] > eqh_level and c["close"] < eqh_level:
            dist  = (c["high"] - eqh_level) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            score = min(1.0, score * (1.0 + 0.1 * (eqh_count - 1)))
            if score >= self.threshold:
                label = "Triple EQH" if eqh_count >= 3 else "EQH"
                return True, score, f"{label} sweep at {eqh_level:.2f} (Score: {score:.2f})"

        lows     = scope["low"].values
        sorted_l = np.sort(lows)
        eql_level, eql_count = None, 1
        for i in range(len(sorted_l) - 1):
            if abs(sorted_l[i + 1] - sorted_l[i]) <= tol:
                eql_level  = (sorted_l[i] + sorted_l[i + 1]) / 2
                eql_count += 1
            elif eql_level is not None:
                break
        if eql_level is not None and c["low"] < eql_level and c["close"] > eql_level:
            dist  = (eql_level - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            score = min(1.0, score * (1.0 + 0.1 * (eql_count - 1)))
            if score >= self.threshold:
                label = "Triple EQL" if eql_count >= 3 else "EQL"
                return True, score, f"{label} sweep at {eql_level:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_asian_range_sweep(self, df):
        if len(df) < self.asian_session_bars + 4:
            return False, 0.0, ""
        atr         = self._calculate_atr(df)
        asian_scope = df.iloc[-(self.asian_session_bars + 1):-1]
        asian_high  = asian_scope["high"].max()
        asian_low   = asian_scope["low"].min()
        asian_range = asian_high - asian_low
        c           = df.iloc[-1]

        if asian_range > atr * 3:
            return False, 0.0, ""

        if c["high"] > asian_high and c["close"] < asian_high:
            dist  = (c["high"] - asian_high) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Asian high sweep at {asian_high:.2f} (Score: {score:.2f})"

        if c["low"] < asian_low and c["close"] > asian_low:
            dist  = (asian_low - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Asian low sweep at {asian_low:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_weekly_range_sweep(self, df):
        if len(df) < self.weekly_lookback + 4:
            return False, 0.0, ""
        atr        = self._calculate_atr(df)
        week_scope = df.iloc[-(self.weekly_lookback + 1):-1]
        weekly_high = week_scope["high"].max()
        weekly_low  = week_scope["low"].min()
        c           = df.iloc[-1]

        if c["high"] > weekly_high and c["close"] < weekly_high:
            dist  = (c["high"] - weekly_high) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Weekly high sweep at {weekly_high:.2f} (Score: {score:.2f})"

        if c["low"] < weekly_low and c["close"] > weekly_low:
            dist  = (weekly_low - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Weekly low sweep at {weekly_low:.2f} (Score: {score:.2f})"

        curr_close = df["close"].iloc[-1]
        if week_scope["high"].max() > weekly_high and curr_close < weekly_high:
            dist  = (week_scope["high"].max() - weekly_high) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.85
            if score >= self.threshold:
                return True, score, f"Historical weekly high swept at {weekly_high:.2f} (Score: {score:.2f})"

        if week_scope["low"].min() < weekly_low and curr_close > weekly_low:
            dist  = (weekly_low - week_scope["low"].min()) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.85
            if score >= self.threshold:
                return True, score, f"Historical weekly low swept at {weekly_low:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _is_near_round_number(self, price, atr):
        tol = self.round_number_tolerance * atr
        for step in [1000, 500, 250, 100, 50]:
            nearest = round(price / step) * step
            if abs(price - nearest) <= tol:
                return True
        return False

    def _detect_round_number_sweep(self, df):
        if len(df) < self.internal_lookback + 4:
            return False, 0.0, ""
        atr = self._calculate_atr(df)
        c   = df.iloc[-1]
        tol = self.round_number_tolerance * atr

        for step in [1000, 500, 250, 100, 50]:
            nearest = round(c["close"] / step) * step
            if c["high"] > nearest + tol and c["close"] < nearest:
                dist  = (c["high"] - nearest) / atr
                score = self._calculate_sweep_quality(True, True, dist)
                score = min(1.0, score * 1.1)
                if score >= self.threshold:
                    return True, score, f"Round number sweep above {nearest:.0f} (Score: {score:.2f})"
            if c["low"] < nearest - tol and c["close"] > nearest:
                dist  = (nearest - c["low"]) / atr
                score = self._calculate_sweep_quality(True, True, dist)
                score = min(1.0, score * 1.1)
                if score >= self.threshold:
                    return True, score, f"Round number sweep below {nearest:.0f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_turtle_soup_sweep(self, df):
        if len(df) < self.internal_lookback + self.turtle_soup_bars + 4:
            return False, 0.0, ""
        atr        = self._calculate_atr(df)
        scope      = df.iloc[-(self.internal_lookback + 1):-1]
        prior_high = scope["high"].max()
        prior_low  = scope["low"].min()
        recent     = df.iloc[-(self.turtle_soup_bars + 1):-1]
        c          = df.iloc[-1]

        if recent["high"].max() > prior_high and c["close"] < prior_high:
            dist  = (recent["high"].max() - prior_high) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Bearish turtle soup above {prior_high:.2f} (Score: {score:.2f})"

        if recent["low"].min() < prior_low and c["close"] > prior_low:
            dist  = (prior_low - recent["low"].min()) / atr
            score = self._calculate_sweep_quality(True, True, dist)
            if score >= self.threshold:
                return True, score, f"Bullish turtle soup below {prior_low:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_inducement_sweep(self, df):
        """
        FIX: original had direction logic inverted.
        Bearish trend = price is falling → institution sweeps HIGHS (not lows)
        to collect liquidity before continuing down.
        Bullish trend = institution sweeps LOWS before continuing up.
        """
        if len(df) < self.major_lookback + 4:
            return False, 0.0, ""
        atr          = self._calculate_atr(df)
        mid_lookback = (self.internal_lookback + self.major_lookback) // 2
        mid_scope    = df.iloc[-(mid_lookback + 1):-1]
        inducement_h = mid_scope["high"].max()
        inducement_l = mid_scope["low"].min()
        c            = df.iloc[-1]
        trend        = self._detect_trend(df)

        # Bearish trend: institution sweeps HIGHS (FIX — was sweeping lows)
        if trend == "bearish" and c["high"] > inducement_h and c["close"] < inducement_h:
            dist  = (c["high"] - inducement_h) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.9
            if score >= self.threshold:
                return True, score, f"Bearish inducement at {inducement_h:.2f} (Score: {score:.2f})"

        # Bullish trend: institution sweeps LOWS (FIX — was sweeping highs)
        if trend == "bullish" and c["low"] < inducement_l and c["close"] > inducement_l:
            dist  = (inducement_l - c["low"]) / atr
            score = self._calculate_sweep_quality(True, True, dist) * 0.9
            if score >= self.threshold:
                return True, score, f"Bullish inducement at {inducement_l:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_retest_sweep(self, df):
        if len(df) < self.historical_sweep_bars + 4:
            return False, 0.0, ""
        atr         = self._calculate_atr(df)
        tol         = self.retest_tolerance_atr * atr
        hist_window = min(self.historical_sweep_bars, len(df) - 2)
        scope       = df.iloc[-(hist_window + 1):-1]
        prior_high  = scope["high"].max()
        prior_low   = scope["low"].min()
        c           = df.iloc[-1]

        swept_high = scope["high"].max() > prior_high
        swept_low  = scope["low"].min()  < prior_low

        if swept_high and abs(c["high"] - prior_high) <= tol and c["close"] < prior_high:
            score = 0.65
            if score >= self.threshold:
                return True, score, f"Retest of swept high at {prior_high:.2f} (Score: {score:.2f})"

        if swept_low and abs(c["low"] - prior_low) <= tol and c["close"] > prior_low:
            score = 0.65
            if score >= self.threshold:
                return True, score, f"Retest of swept low at {prior_low:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    def _detect_ote_sweep(self, df):
        """
        OTE sweep using internal_lookback scope for consistency with other detectors.
        FIX: original used a hardcoded 20-bar scope for swing_high/swing_low
        while the trend detection used a different 20-bar scope (often not
        the same 20 bars). Now both use self.internal_lookback.
        """
        if len(df) < self.internal_lookback + 8:
            return False, 0.0, ""
        atr   = self._calculate_atr(df)
        scope = df.iloc[-(self.internal_lookback + 1):-1]
        swing_high = scope["high"].max()
        swing_low  = scope["low"].min()
        c          = df.iloc[-1]
        trend      = self._detect_trend(df, lookback=self.internal_lookback)

        if trend == "bearish":
            leg_size = swing_high - swing_low
            if leg_size <= 0:
                return False, 0.0, ""
            ote_low  = swing_high - leg_size * 0.79
            ote_high = swing_high - leg_size * 0.618
            if ote_low <= c["close"] <= ote_high and c["close"] < swing_high:
                dist  = (swing_high - c["close"]) / atr
                score = min(0.85, self._calculate_sweep_quality(True, True, dist) * 0.9)
                if score >= self.threshold:
                    return True, score, f"Bearish OTE zone {ote_low:.2f}–{ote_high:.2f} (Score: {score:.2f})"

        if trend == "bullish":
            leg_size = swing_high - swing_low
            if leg_size <= 0:
                return False, 0.0, ""
            ote_low  = swing_low + leg_size * 0.618
            ote_high = swing_low + leg_size * 0.79
            if ote_low <= c["close"] <= ote_high and c["close"] > swing_low:
                dist  = (c["close"] - swing_low) / atr
                score = min(0.85, self._calculate_sweep_quality(True, True, dist) * 0.9)
                if score >= self.threshold:
                    return True, score, f"Bullish OTE zone {ote_low:.2f}–{ote_high:.2f} (Score: {score:.2f})"

        return False, 0.0, ""

    # ─────────────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────────────

    def validate(self, df) -> Tuple[bool, float]:
        """
        FIX: self._reason is set from the winning detector so base.process()
        can read it. Previously only _check_sweep_enhanced set the reason.
        """
        min_required = self.internal_lookback + 2
        if len(df) < min_required:
            logger.warning(f"[VALIDATE] Insufficient bars: {len(df)} < {min_required}")
            return False, 0.0

        trend = self._detect_trend(df)
        atr   = self._calculate_atr(df)

        # 1. Internal sweep
        if self.enable_internal:
            int_h, int_l = self._find_swing_points(df, self.internal_lookback)
            found, score, reason = self._check_sweep_enhanced(df, int_l, int_h, is_internal=True)
            if found:
                self._reason = reason
                self._bias   = self._bias_from_reason(reason)
                return True, score

        # 2. Major sweep
        maj_h, maj_l = self._find_swing_points(df, self.major_lookback)
        found, score, reason = self._check_sweep_enhanced(df, maj_l, maj_h, is_internal=False)
        if found:
            self._reason = reason
            self._bias   = self._bias_from_reason(reason)
            return True, score

        # 3. Gold-specific detectors
        for label, detector in [
            ("STOP_HUNT",    self._detect_stop_hunt_sweep),
            ("BSL_SSL",      self._detect_bsl_ssl_sweep),
            ("PDH_PDL",      self._detect_pdh_pdl_sweep),
            ("WEEKLY",       self._detect_weekly_range_sweep),
            ("EQH_EQL",      self._detect_eqh_eql_sweep),
            ("ROUND_NUMBER", self._detect_round_number_sweep),
            ("ASIAN_RANGE",  self._detect_asian_range_sweep),
            ("TURTLE_SOUP",  self._detect_turtle_soup_sweep),
            ("OTE",          self._detect_ote_sweep),
            ("INDUCEMENT",   self._detect_inducement_sweep),
            ("RETEST",       self._detect_retest_sweep),
        ]:
            detected, det_score, det_reason = detector(df)
            if detected:
                logger.info(f"{label} SWEEP: {det_reason}")
                self._reason = det_reason
                self._bias   = self._bias_from_reason(det_reason)
                return True, det_score

        self._reason = "No qualifying sweep"
        self._bias   = "neutral"
        return False, 0.0

    def _adapt_lookbacks(self, n_bars):
        cap = max(n_bars - 4, self.internal_lookback)
        self.major_lookback        = min(self.major_lookback,        cap)
        self.historical_sweep_bars = min(self.historical_sweep_bars, cap)
        self.pdh_pdl_lookback      = min(self.pdh_pdl_lookback,      cap)
        self.asian_session_bars    = min(self.asian_session_bars,     cap)
        self.weekly_lookback       = min(self.weekly_lookback,        cap)
        self.bsl_revert_candles    = min(self.bsl_revert_candles,     cap)
        self.ssl_revert_candles    = min(self.ssl_revert_candles,     cap)

    def process(self, data):
        """
        FIX: result dict now always contains 'bias' key derived from sweep
        direction. The bootstrapper uses result["bias"] to set signal direction.
        """
        tf_key  = self.config.get("timeframe_key", "m5_candles")
        candles = data.get(tf_key, [])
        if not candles:
            return {"status": False, "reason": f"{self.name}: No {tf_key} data",
                    "score": 0.0, "bias": "neutral"}
        df = pd.DataFrame(candles)
        self._adapt_lookbacks(len(df))

        status, score = self.validate(df)
        return {
            "status": status,
            "reason": f"SMC {self.name}: {'Qualified' if status else 'Rejected'} — {self._reason}",
            "score":  score,
            "bias":   self._bias,
        }
