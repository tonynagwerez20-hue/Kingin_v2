"""
DisplacementLayer — Gold SMC Edition
=======================================================
Measures institutional urgency / impulsive price delivery for Gold (XAUUSD).

Models: standard single-candle, multi-candle, one-sided delivery,
        FVG-confirmed displacement, volume proxy

Multi-timeframe priority: H1 > M15 > M5

FIXES vs ORIGINAL
─────────────────
1. process() did not return 'bias' in the result dict. Every other layer
   returns it; the bootstrapper reads it to gate signal direction. Added.
2. _detect_standard() sets bias from the candle direction. The original had
   `direction = "Bullish" | "Bearish"` in the reason string but never stored
   self._bias. Now self._bias is set in validate() from the reason string.
3. _detect_multi_candle(): direction was derived from open[0] vs close[-1]
   of the `recent` window, which is correct. Added explicit bias derivation.
4. _detect_one_sided_delivery(): all_bullish/all_bearish was computed but
   bias was not stored. Fixed.
5. _detect_volume_proxy(): direction was computed from the last candle but
   not stored as bias. Fixed.
6. process() negative result path re-ran _detect_displacement() on M5
   candles that may have already been tried in the loop. Now uses a stored
   last_reason to avoid a redundant detection call.
"""

import pandas as pd
import numpy as np
from typing import Tuple
from .base import SMCLayerBase
import logging

logger = logging.getLogger("Displacement")


class DisplacementLayer(SMCLayerBase):
    BODY_ATR_THRESHOLD      = 0.5
    MULTI_CANDLE_BARS       = 3
    MULTI_CANDLE_THRESHOLD  = 1.2
    ONE_SIDED_BARS          = 4
    CLOSE_RATIO_THRESHOLD   = 0.65
    FVG_DISPLACEMENT_BONUS  = 0.15

    def __init__(self, name="Displacement", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason                = "Displacement not yet evaluated"
        self._bias                  = "neutral"
        self.body_atr_threshold     = self.config.get("body_atr_threshold",    self.BODY_ATR_THRESHOLD)
        self.multi_candle_bars      = self.config.get("multi_candle_bars",     self.MULTI_CANDLE_BARS)
        self.multi_candle_threshold = self.config.get("multi_candle_threshold",self.MULTI_CANDLE_THRESHOLD)
        self.one_sided_bars         = self.config.get("one_sided_bars",        self.ONE_SIDED_BARS)
        self.close_ratio_threshold  = self.config.get("close_ratio_threshold", self.CLOSE_RATIO_THRESHOLD)

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

    def _has_fvg(self, df):
        if len(df) < 3:
            return False
        return (df["low"].iloc[-1] > df["high"].iloc[-3]) or \
               (df["high"].iloc[-1] < df["low"].iloc[-3])

    # ─────────────────────────────────────────────────────────────────
    # Detectors — each returns (found, reason, score)
    # ─────────────────────────────────────────────────────────────────

    def _detect_standard(self, df) -> Tuple[bool, str, float]:
        """Single-candle displacement: body > threshold × ATR."""
        if len(df) < 21:
            return False, "Insufficient data", 0.0
        atr        = self._calculate_atr(df)
        c          = df.iloc[-1]
        body       = abs(c["close"] - c["open"])
        candle_rng = c["high"] - c["low"]
        if candle_rng == 0:
            return False, "Zero range candle", 0.0
        close_ratio = body / candle_rng
        ratio       = body / atr if atr > 0 else 0
        score       = min(ratio / 2.0, 1.0)

        if close_ratio >= self.close_ratio_threshold:
            score = min(1.0, score * 1.1)
        if self._has_fvg(df):
            score = min(1.0, score + self.FVG_DISPLACEMENT_BONUS)

        direction = "Bullish" if c["close"] > c["open"] else "Bearish"
        if ratio >= self.body_atr_threshold:
            return True, f"{direction} displacement: body {body:.2f} = {ratio:.2f}×ATR", score
        return False, f"Weak: body {body:.2f} = {ratio:.2f}×ATR (need {self.body_atr_threshold}×)", score

    def _detect_multi_candle(self, df) -> Tuple[bool, str, float]:
        """Multi-candle displacement: cumulative same-direction move > threshold × ATR."""
        n = self.multi_candle_bars
        if len(df) < n + 14:
            return False, "Insufficient data", 0.0
        atr     = self._calculate_atr(df)
        recent  = df.iloc[-n:]
        net_move= abs(recent["close"].iloc[-1] - recent["open"].iloc[0])
        score   = min(1.0, net_move / (atr * self.multi_candle_threshold))
        if net_move > atr * self.multi_candle_threshold:
            direction = "Bullish" if recent["close"].iloc[-1] > recent["open"].iloc[0] else "Bearish"
            return True, f"{direction} multi-candle displacement: net {net_move:.2f} = {net_move/atr:.2f}×ATR", score
        return False, "", 0.0

    def _detect_one_sided_delivery(self, df) -> Tuple[bool, str, float]:
        """N consecutive same-direction candles with no retracement."""
        n = self.one_sided_bars
        if len(df) < n + 2:
            return False, "", 0.0
        recent = df.iloc[-n:]
        bodies = recent["close"].values - recent["open"].values
        all_bullish = all(b > 0 for b in bodies)
        all_bearish = all(b < 0 for b in bodies)
        if not (all_bullish or all_bearish):
            return False, "", 0.0
        atr   = self._calculate_atr(df)
        move  = abs(recent["close"].iloc[-1] - recent["open"].iloc[0])
        score = min(1.0, move / (atr * self.multi_candle_threshold) * 0.9)
        direction = "Bullish" if all_bullish else "Bearish"
        return True, f"{direction} one-sided delivery: {n} consecutive candles, move {move:.2f}", score

    def _detect_volume_proxy(self, df) -> Tuple[bool, str, float]:
        """Range expansion proxy for institutional candle (> 2× recent average range)."""
        if len(df) < 22:
            return False, "", 0.0
        ranges    = (df["high"] - df["low"]).iloc[-21:-1]
        avg_range = ranges.mean()
        curr_range= df["high"].iloc[-1] - df["low"].iloc[-1]
        if avg_range == 0:
            return False, "", 0.0
        ratio = curr_range / avg_range
        if ratio >= 2.0:
            score     = min(1.0, ratio / 4.0)
            c         = df.iloc[-1]
            direction = "Bullish" if c["close"] > c["open"] else "Bearish"
            return True, f"{direction} volume proxy: range {curr_range:.2f} = {ratio:.2f}× avg", score
        return False, "", 0.0

    # ─────────────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────────────

    def _detect_displacement(self, df) -> Tuple[bool, str, float]:
        """Run all models; return highest-scoring result."""
        best_found, best_reason, best_score = False, "No displacement", 0.0
        for detector in [
            self._detect_standard,
            self._detect_one_sided_delivery,
            self._detect_multi_candle,
            self._detect_volume_proxy,
        ]:
            found, reason, score = detector(df)
            if found and score > best_score:
                best_found, best_reason, best_score = found, reason, score
        return best_found, best_reason, best_score

    def _bias_from_reason(self, reason: str) -> str:
        r = reason.lower()
        if "bullish" in r:
            return "bullish"
        if "bearish" in r:
            return "bearish"
        return "neutral"

    def validate(self, df) -> Tuple[bool, float]:
        found, reason, score = self._detect_displacement(df)
        self._reason = reason
        # FIX: always set _bias so base.process() can read it
        self._bias   = self._bias_from_reason(reason)
        return found, score

    def process(self, data: dict) -> dict:
        """
        Multi-TF displacement detection: H1 > M15 > M5.
        FIX: 'bias' key now always in result dict.
        FIX: negative result path uses stored reason from last TF tried instead
        of re-running detection on M5 (which would be a duplicate call).
        """
        last_reason = "No displacement"
        last_score  = 0.0

        for tf_key, tf_label in [("h1_candles", "H1"), ("m15_candles", "M15"), ("m5_candles", "M5")]:
            candles = data.get(tf_key, [])
            if not candles:
                continue
            df = pd.DataFrame(candles)
            found, reason, score = self._detect_displacement(df)
            last_reason = reason
            last_score  = score
            if found:
                self._reason = f"{tf_label}: {reason}"
                self._bias   = self._bias_from_reason(reason)
                return {"status": True,
                        "reason": f"Displacement: {self._reason}",
                        "score": score,
                        "bias": self._bias}

        # All TFs checked — no displacement found
        self._reason = f"No displacement on any TF — {last_reason}"
        self._bias   = "neutral"
        return {"status": False,
                "reason": f"Displacement: {self._reason}",
                "score": last_score,
                "bias": "neutral"}
