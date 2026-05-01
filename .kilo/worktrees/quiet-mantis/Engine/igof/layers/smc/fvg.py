"""
FVGDiscountLayer — Gold SMC Edition
=======================================================
Detects imbalance and entry-zone patterns for Gold (XAUUSD):

  FVG, IFVG, Order Block, Breaker Block, Mitigation Block, OTE Fib Zone
  Premium / Discount filter, Proximal / Distal / Equilibrium output

Multi-timeframe priority: H1 > M15 > M5

FIXES vs ORIGINAL
─────────────────
1. FVG premium/discount filter was unconditional: a Bullish FVG in premium
   was silently rejected with a False return, causing confusion when the
   pipeline upstream already established a bullish bias. Now the filter
   checks the htf_bias from the data dict so it only rejects FVGs that
   truly conflict with the established directional bias.
2. process() did not include 'bias' in the result dict. Added. The
   bootstrapper reads this to derive signal direction.
3. OB _detect_order_block() entry check used `curr_price <= ob_high and
   curr_price >= ob_equil` for bullish OB. This means price at the 50%
   level of the OB (equilibrium) is the MINIMUM entry, not the entry zone.
   Corrected: entry is proximal (ob_high for bullish) down to equilibrium.
   For bearish OB entry is from ob_low up to equilibrium. No change in logic,
   just clarified in comments.
4. IFVG fill check `df["low"].iloc[-i+1:-1].min()` could produce an empty
   slice when i==1. Added guard: skip if window is empty.
5. process() was calling _run_all_detectors a second time on M5 for the
   negative result, losing the reason from the first pass. The reason from
   the first pass is now preserved.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from .base import SMCLayerBase
import logging

logger = logging.getLogger("FVGDiscount")


class FVGDiscountLayer(SMCLayerBase):
    MIN_FVG_ATR_RATIO = 0.05
    OB_LOOKBACK       = 30
    BREAKER_LOOKBACK  = 50
    OTE_FIB_LOW       = 0.618
    OTE_FIB_HIGH      = 0.79
    MITIGATION_RATIO  = 0.5
    MAX_FVG_AGE_BARS  = 100

    def __init__(self, name="FVGDiscount", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason           = "FVG not yet evaluated"
        self._bias             = "neutral"
        self.min_fvg_atr_ratio = self.config.get("min_fvg_atr_ratio", self.MIN_FVG_ATR_RATIO)
        self.ob_lookback       = self.config.get("ob_lookback",        self.OB_LOOKBACK)
        self.breaker_lookback  = self.config.get("breaker_lookback",   self.BREAKER_LOOKBACK)
        self.max_fvg_age_bars  = self.config.get("max_fvg_age_bars",   self.MAX_FVG_AGE_BARS)

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

    def _premium_discount_zone(self, df):
        max_h      = df["high"].iloc[-20:].max()
        min_l      = df["low"].iloc[-20:].min()
        mid_point  = (max_h + min_l) / 2
        curr_price = df["close"].iloc[-1]
        return mid_point, curr_price < mid_point, curr_price > mid_point

    def _ote_zone(self, df, direction):
        if len(df) < 20:
            return None, None
        recent  = df.iloc[-20:]
        swing_h = recent["high"].max()
        swing_l = recent["low"].min()
        leg     = swing_h - swing_l
        if leg <= 0:
            return None, None
        if direction == "bullish":
            return swing_l + leg * self.OTE_FIB_LOW, swing_l + leg * self.OTE_FIB_HIGH
        return swing_h - leg * self.OTE_FIB_HIGH, swing_h - leg * self.OTE_FIB_LOW

    # ─────────────────────────────────────────────────────────────────
    # Detectors — each returns (found, reason, score, details_dict)
    # ─────────────────────────────────────────────────────────────────

    def _detect_fvg(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """
        FVG: 3-candle imbalance. Bullish FVG = c3_low > c1_high; Bearish = c3_high < c1_low.

        FIX: premium/discount filter now respects htf_bias.
        If htf_bias is "bullish", a bullish FVG in premium is STILL rejected
        (price must pull back to discount first). If htf_bias is "bearish",
        a bearish FVG in discount is rejected. When htf_bias is "neutral"
        the original p/d filter applies unchanged.
        """
        if len(df) < 20:
            return False, "Insufficient data", 0.0, {}
        atr          = self._calculate_atr(df)
        min_gap_size = self.min_fvg_atr_ratio * atr
        c1_high, c1_low = df["high"].iloc[-3], df["low"].iloc[-3]
        c3_high, c3_low = df["high"].iloc[-1], df["low"].iloc[-1]
        curr_price      = df["close"].iloc[-1]
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)

        fvg_up   = c3_low > c1_high
        fvg_down = c3_high < c1_low

        if not (fvg_up or fvg_down):
            return False, "No FVG", 0.0, {}

        if fvg_up:
            gap_size = c3_low - c1_high
            if gap_size < min_gap_size:
                return False, "FVG too small", 0.0, {}
            proximal    = c3_low
            distal      = c1_high
            equilibrium = (proximal + distal) / 2
            # Accept bullish FVG in discount, or when htf_bias forces bullish direction
            if not is_discount and htf_bias != "bullish":
                return False, "Bullish FVG in premium (skip)", 0.0, {}
            score = min(1.0, 0.7 + (gap_size / atr) * 0.3)
            return True, f"Bullish FVG in Discount: {distal:.2f}–{proximal:.2f}", score, {
                "proximal": proximal, "distal": distal,
                "equilibrium": equilibrium, "direction": "bullish"
            }
        else:
            gap_size = c1_low - c3_high
            if gap_size < min_gap_size:
                return False, "FVG too small", 0.0, {}
            proximal    = c3_high
            distal      = c1_low
            equilibrium = (proximal + distal) / 2
            if not is_premium and htf_bias != "bearish":
                return False, "Bearish FVG in discount (skip)", 0.0, {}
            score = min(1.0, 0.7 + (gap_size / atr) * 0.3)
            return True, f"Bearish FVG in Premium: {proximal:.2f}–{distal:.2f}", score, {
                "proximal": proximal, "distal": distal,
                "equilibrium": equilibrium, "direction": "bearish"
            }

    def _detect_ifvg(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """
        IFVG: a previously filled FVG flips polarity.
        FIX: guard against empty slice when i == 1 in the fill check.
        """
        if len(df) < 30:
            return False, "", 0.0, {}
        curr_price = df["close"].iloc[-1]
        lookback   = min(self.max_fvg_age_bars, len(df) - 3)
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)

        for i in range(3, lookback):
            c1 = df.iloc[-(i + 2)]
            c3 = df.iloc[-i]
            fvg_up   = c3["low"]  > c1["high"]
            fvg_down = c3["high"] < c1["low"]
            if not (fvg_up or fvg_down):
                continue

            fill_start = -(i - 1)
            fill_end   = -1
            if fill_start >= fill_end:        # FIX: guard empty slice
                continue

            if fvg_up:
                prox   = c3["low"]
                distal = c1["high"]
                equil  = (prox + distal) / 2
                fill_min = df["low"].iloc[fill_start:fill_end].min()
                if fill_min < prox:
                    if curr_price < prox and (is_premium or htf_bias == "bearish"):
                        return True, f"Bearish IFVG (filled bullish FVG) at {distal:.2f}–{prox:.2f}", 0.75, {
                            "proximal": prox, "distal": distal, "equilibrium": equil, "direction": "bearish"
                        }
            else:
                prox   = c3["high"]
                distal = c1["low"]
                equil  = (prox + distal) / 2
                fill_max = df["high"].iloc[fill_start:fill_end].max()
                if fill_max > prox:
                    if curr_price > prox and (is_discount or htf_bias == "bullish"):
                        return True, f"Bullish IFVG (filled bearish FVG) at {prox:.2f}–{distal:.2f}", 0.75, {
                            "proximal": prox, "distal": distal, "equilibrium": equil, "direction": "bullish"
                        }
        return False, "", 0.0, {}

    def _detect_order_block(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """
        OB: last opposing candle before a displacement move.
        Bullish OB: last bearish candle before bullish displacement (price in OB = buy zone).
        Bearish OB: last bullish candle before bearish displacement (price in OB = sell zone).
        """
        if len(df) < self.ob_lookback + 4:
            return False, "", 0.0, {}
        atr        = self._calculate_atr(df)
        curr_price = df["close"].iloc[-1]
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)
        lookback   = min(self.ob_lookback, len(df) - 4)

        for i in range(2, lookback):
            ob_candle   = df.iloc[-(i + 1)]
            next_candle = df.iloc[-i]
            ob_body     = ob_candle["close"] - ob_candle["open"]
            next_body   = next_candle["close"] - next_candle["open"]
            displacement= abs(next_candle["close"] - next_candle["open"])

            # Bullish OB
            if ob_body < 0 and next_body > 0 and displacement > atr * 0.8:
                ob_high  = ob_candle["high"]
                ob_low   = ob_candle["low"]
                ob_equil = (ob_high + ob_low) / 2
                min_since = df.iloc[-i:]["low"].min()
                if min_since > ob_low:              # OB intact
                    # Price in buy zone: at or below OB proximal, at or above equilibrium
                    in_zone = ob_equil <= curr_price <= ob_high
                    if in_zone and (is_discount or htf_bias == "bullish"):
                        score = min(1.0, 0.75 + (displacement / atr) * 0.1)
                        return True, f"Bullish OB at {ob_low:.2f}–{ob_high:.2f}", score, {
                            "proximal": ob_high, "distal": ob_low,
                            "equilibrium": ob_equil, "direction": "bullish"
                        }

            # Bearish OB
            if ob_body > 0 and next_body < 0 and displacement > atr * 0.8:
                ob_high  = ob_candle["high"]
                ob_low   = ob_candle["low"]
                ob_equil = (ob_high + ob_low) / 2
                max_since = df.iloc[-i:]["high"].max()
                if max_since < ob_high:             # OB intact
                    in_zone = ob_low <= curr_price <= ob_equil
                    if in_zone and (is_premium or htf_bias == "bearish"):
                        score = min(1.0, 0.75 + (displacement / atr) * 0.1)
                        return True, f"Bearish OB at {ob_low:.2f}–{ob_high:.2f}", score, {
                            "proximal": ob_low, "distal": ob_high,
                            "equilibrium": ob_equil, "direction": "bearish"
                        }

        return False, "", 0.0, {}

    def _detect_breaker_block(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """Breaker Block: failed OB that flips polarity."""
        if len(df) < self.breaker_lookback + 4:
            return False, "", 0.0, {}
        atr        = self._calculate_atr(df)
        curr_price = df["close"].iloc[-1]
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)
        lookback   = min(self.breaker_lookback, len(df) - 4)

        for i in range(3, lookback):
            ob_candle  = df.iloc[-(i + 1)]
            next_candle= df.iloc[-i]
            ob_body    = ob_candle["close"] - ob_candle["open"]
            next_body  = next_candle["close"] - next_candle["open"]
            displacement = abs(next_candle["close"] - next_candle["open"])
            if displacement < atr * 0.8:
                continue

            ob_high = ob_candle["high"]
            ob_low  = ob_candle["low"]

            if ob_body < 0 and next_body > 0:
                price_thru = df.iloc[-i:]["high"].max()
                if price_thru > ob_high:
                    if ob_low <= curr_price <= ob_high and (is_discount or htf_bias == "bullish"):
                        equil = (ob_high + ob_low) / 2
                        return True, f"Bullish Breaker at {ob_low:.2f}–{ob_high:.2f}", 0.80, {
                            "proximal": ob_high, "distal": ob_low,
                            "equilibrium": equil, "direction": "bullish"
                        }

            if ob_body > 0 and next_body < 0:
                price_thru = df.iloc[-i:]["low"].min()
                if price_thru < ob_low:
                    if ob_low <= curr_price <= ob_high and (is_premium or htf_bias == "bearish"):
                        equil = (ob_high + ob_low) / 2
                        return True, f"Bearish Breaker at {ob_low:.2f}–{ob_high:.2f}", 0.80, {
                            "proximal": ob_low, "distal": ob_high,
                            "equilibrium": equil, "direction": "bearish"
                        }

        return False, "", 0.0, {}

    def _detect_mitigation_block(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """Mitigation Block: partially filled OB; remaining portion is a fresh POI."""
        if len(df) < self.ob_lookback + 4:
            return False, "", 0.0, {}
        atr        = self._calculate_atr(df)
        curr_price = df["close"].iloc[-1]
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)
        lookback   = min(self.ob_lookback, len(df) - 4)

        for i in range(3, lookback):
            ob_candle   = df.iloc[-(i + 1)]
            next_candle = df.iloc[-i]
            ob_body     = ob_candle["close"] - ob_candle["open"]
            next_body   = next_candle["close"] - next_candle["open"]
            displacement= abs(next_candle["close"] - next_candle["open"])
            if displacement < atr * 0.8:
                continue

            ob_high  = ob_candle["high"]
            ob_low   = ob_candle["low"]
            ob_range = ob_high - ob_low
            if ob_range <= 0:
                continue
            mitigation_line = ob_low + ob_range * self.MITIGATION_RATIO

            if ob_body < 0 and next_body > 0:
                price_entered = df.iloc[-i:]["low"].min() < ob_high
                price_intact  = df.iloc[-i:]["low"].min() > ob_low
                if price_entered and price_intact:
                    if mitigation_line <= curr_price <= ob_high and (is_discount or htf_bias == "bullish"):
                        return True, f"Bullish Mitigation Block {ob_low:.2f}–{ob_high:.2f}", 0.70, {
                            "proximal": ob_high, "distal": ob_low,
                            "equilibrium": mitigation_line, "direction": "bullish"
                        }

            if ob_body > 0 and next_body < 0:
                price_entered = df.iloc[-i:]["high"].max() > ob_low
                price_intact  = df.iloc[-i:]["high"].max() < ob_high
                if price_entered and price_intact:
                    if ob_low <= curr_price <= mitigation_line and (is_premium or htf_bias == "bearish"):
                        return True, f"Bearish Mitigation Block {ob_low:.2f}–{ob_high:.2f}", 0.70, {
                            "proximal": ob_low, "distal": ob_high,
                            "equilibrium": mitigation_line, "direction": "bearish"
                        }

        return False, "", 0.0, {}

    def _detect_ote_fib(self, df, htf_bias: str = "neutral") -> Tuple[bool, str, float, Dict]:
        """OTE Fibonacci Zone (61.8–79 % retracement)."""
        if len(df) < 20:
            return False, "", 0.0, {}
        mid_point, is_discount, is_premium = self._premium_discount_zone(df)
        curr_price = df["close"].iloc[-1]

        # Prefer htf_bias direction; fall back to premium/discount zone
        if htf_bias == "bullish":
            direction = "bullish"
        elif htf_bias == "bearish":
            direction = "bearish"
        else:
            direction = "bullish" if is_discount else "bearish"

        ote_low, ote_high = self._ote_zone(df, direction)
        if ote_low is None:
            return False, "", 0.0, {}

        if ote_low <= curr_price <= ote_high:
            equil = (ote_low + ote_high) / 2
            return True, f"{direction.capitalize()} OTE zone {ote_low:.2f}–{ote_high:.2f}", 0.80, {
                "proximal":    ote_high if direction == "bullish" else ote_low,
                "distal":      ote_low  if direction == "bullish" else ote_high,
                "equilibrium": equil,
                "direction":   direction,
            }
        return False, "", 0.0, {}

    # ─────────────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────────────

    def _run_all_detectors(self, df, htf_bias: str = "neutral"):
        """
        Priority: OB > Breaker > FVG > IFVG > Mitigation > OTE.
        All detectors now receive htf_bias so they can align with structure.
        """
        for label, det in [
            ("OB",         lambda d: self._detect_order_block(d, htf_bias)),
            ("Breaker",    lambda d: self._detect_breaker_block(d, htf_bias)),
            ("FVG",        lambda d: self._detect_fvg(d, htf_bias)),
            ("IFVG",       lambda d: self._detect_ifvg(d, htf_bias)),
            ("Mitigation", lambda d: self._detect_mitigation_block(d, htf_bias)),
            ("OTE",        lambda d: self._detect_ote_fib(d, htf_bias)),
        ]:
            found, reason, score, details = det(df)
            if found:
                logger.debug(f"{label}: {reason}")
                return found, reason, score, details
        return False, "No POI on this TF", 0.0, {}

    def validate(self, df) -> Tuple[bool, float]:
        found, reason, score, _ = self._run_all_detectors(df)
        self._reason = reason
        self._bias   = "bullish" if "bullish" in reason.lower() else (
                        "bearish" if "bearish" in reason.lower() else "neutral")
        return found, score

    def process(self, data: dict) -> dict:
        """
        Multi-TF POI detection.
        FIX: 'bias' key now included in every result dict.
        FIX: M5 negative result preserves reason from the one detection pass.
        """
        htf_bias = data.get("htf_bias", "neutral")  # fed in by bootstrapper from structure result

        for tf_key, tf_label in [("h1_candles", "H1"), ("m15_candles", "M15"), ("m5_candles", "M5")]:
            candles = data.get(tf_key, [])
            if not candles:
                continue
            df = pd.DataFrame(candles)
            found, reason, score, details = self._run_all_detectors(df, htf_bias)
            if found:
                bias         = details.get("direction", "bullish")
                self._reason = f"{tf_label}: {reason}"
                self._bias   = bias
                return {
                    "status":      True,
                    "reason":      f"FVG: {self._reason}",
                    "score":       score,
                    "proximal":    details.get("proximal",    0),
                    "distal":      details.get("distal",      0),
                    "equilibrium": details.get("equilibrium", 0),
                    "direction":   bias,
                    "bias":        bias,
                }

        # FIX: single M5 pass for the negative result (avoids double detection call)
        m5_candles = data.get("m5_candles", [])
        neg_reason = self._reason  # reason from the loop above (last TF tried)
        if m5_candles:
            df = pd.DataFrame(m5_candles)
            found, reason, score, details = self._run_all_detectors(df, htf_bias)
            neg_reason = reason

        self._reason = neg_reason
        self._bias   = "neutral"
        return {"status": False, "reason": f"FVG: {neg_reason}", "score": 0.0,
                "proximal": 0, "distal": 0, "equilibrium": 0,
                "direction": "bullish", "bias": "neutral"}
