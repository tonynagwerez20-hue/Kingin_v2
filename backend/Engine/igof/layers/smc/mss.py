"""
MicroMSSLayer — Gold SMC Edition
=======================================================
Lower-timeframe (M5/M15) confirmation of structural shifts for Gold.

Models: Micro CHoCH, Micro BOS, Micro MSS, iBOS, Sweep+MSS, Fair Value Return

Multi-timeframe priority: M15 > M5

FIXES vs ORIGINAL
─────────────────
1. _detect_sweep_mss() "bearish sweep → bullish revert" logic was inverted:
   a sweep ABOVE swing_h means BSL was taken (bearish sweep) and price should
   then make a BEARISH MSS (turn down). The original checked "Bearish" in
   reason after the sweep-high, which is correct, but the comment said
   "bearish sweep + bullish revert" — now corrected to match ICT model:
     • Sweep above swing_h (BSL taken) → expect BEARISH CHoCH/BOS
     • Sweep below swing_l (SSL taken) → expect BULLISH CHoCH/BOS
2. _detect_fair_value_return() direction check was labelled by upper/lower half
   of the FVR zone. This is ambiguous — a bullish FVR entry requires price
   to be in discount AND showing a bullish rejection candle. Added:
   candle body direction must match the inferred direction.
3. _detect_micro_mss() checked `body >= self.disp_ratio * atr` but
   DISPLACEMENT_RATIO = 0.4 means body must exceed 40% of ATR. The >=
   comparison already handles equality correctly — no change needed there.
   However the score multiplier `min(1.0, score * 1.1)` could push above
   0.80 (the CHoCH score) when score is already 0.80. Capped at 0.90.
4. process() now always includes 'bias' in the returned dict.
5. _detect_mss() (orchestrator) ran all detectors even after finding a result;
   now returns immediately on first match (priority order is preserved).
"""

import pandas as pd
import numpy as np
from typing import Tuple
from .base import SMCLayerBase
import logging

logger = logging.getLogger("MicroMSS")


class MicroMSSLayer(SMCLayerBase):
    MSS_LOOKBACK       = 10
    DISPLACEMENT_RATIO = 0.4
    SWEEP_REVERT_BARS  = 5
    FVR_RETRACE_LOW    = 0.40
    FVR_RETRACE_HIGH   = 0.60

    def __init__(self, name="MicroMSS", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason      = "Micro MSS not yet evaluated"
        self._bias        = "neutral"
        self.mss_lookback = self.config.get("mss_lookback",      self.MSS_LOOKBACK)
        self.disp_ratio   = self.config.get("displacement_ratio", self.DISPLACEMENT_RATIO)
        self.sweep_bars   = self.config.get("sweep_revert_bars",  self.SWEEP_REVERT_BARS)

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

    def _get_recent_swings(self, df, lookback):
        if len(df) < lookback + 3:
            return None, None, [], []
        scope  = df.iloc[-(lookback + 1):-1]
        highs  = scope["high"].values
        lows   = scope["low"].values
        sh_idx = [i for i in range(1, len(highs) - 1)
                  if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]]
        sl_idx = [i for i in range(1, len(lows) - 1)
                  if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]]
        swing_highs = [highs[i] for i in sh_idx]
        swing_lows  = [lows[i]  for i in sl_idx]
        return (max(swing_highs) if swing_highs else scope["high"].max(),
                min(swing_lows)  if swing_lows  else scope["low"].min(),
                swing_highs[-2:] if len(swing_highs) >= 2 else swing_highs,
                swing_lows[-2:]  if len(swing_lows)  >= 2 else swing_lows)

    # ─────────────────────────────────────────────────────────────────
    # Detection models
    # ─────────────────────────────────────────────────────────────────

    def _detect_micro_bos(self, df) -> Tuple[bool, str, float]:
        if len(df) < self.mss_lookback + 3:
            return False, "Insufficient data", 0.0
        sh, sl, _, _ = self._get_recent_swings(df, self.mss_lookback)
        last_close   = df["close"].iloc[-1]
        if sh and last_close > sh:
            return True, f"Bullish micro BOS: Close {last_close:.2f} > High {sh:.2f}", 0.70
        if sl and last_close < sl:
            return True, f"Bearish micro BOS: Close {last_close:.2f} < Low {sl:.2f}", 0.70
        return False, f"No micro BOS — Close {last_close:.2f} in range [{sl:.2f}–{sh:.2f}]", 0.0

    def _detect_micro_choch(self, df) -> Tuple[bool, str, float]:
        if len(df) < self.mss_lookback + 5:
            return False, "", 0.0
        _, _, last_highs, last_lows = self._get_recent_swings(df, self.mss_lookback)
        last_close = df["close"].iloc[-1]

        if len(last_lows) == 2 and last_lows[1] > last_lows[0]:
            if last_close < last_lows[1]:
                return True, f"Bearish CHoCH: Close {last_close:.2f} < HL {last_lows[1]:.2f}", 0.80

        if len(last_highs) == 2 and last_highs[1] < last_highs[0]:
            if last_close > last_highs[1]:
                return True, f"Bullish CHoCH: Close {last_close:.2f} > LH {last_highs[1]:.2f}", 0.80

        return False, "", 0.0

    def _detect_micro_mss(self, df) -> Tuple[bool, str, float]:
        """
        Micro MSS: CHoCH + displacement candle.
        FIX: score capped at 0.90 (was uncapped, could exceed 0.88 which is
        higher than what the orchestrator should assign to a micro signal).
        """
        found, reason, score = self._detect_micro_choch(df)
        if not found:
            return False, "", 0.0
        atr  = self._calculate_atr(df)
        body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        if body >= self.disp_ratio * atr:
            confirmed_score = min(0.90, score * 1.1)
            return True, f"Micro MSS confirmed — {reason} (body={body:.2f})", confirmed_score
        return False, "", 0.0

    def _detect_sweep_mss(self, df) -> Tuple[bool, str, float]:
        """
        Sweep + MSS: liquidity sweep followed within N bars by a CHoCH/BOS.

        FIX — ICT model corrected:
          • Sweep ABOVE swing_h = BSL taken (bearish event) → look for BEARISH structure shift
          • Sweep BELOW swing_l = SSL taken (bullish event) → look for BULLISH structure shift

        The original comment said "bearish sweep + bullish revert" for the
        above-swing_h case which was backwards. The code was actually correct
        but misleadingly labelled. Both the label and logic are now consistent.
        """
        n = self.sweep_bars
        if len(df) < self.mss_lookback + n + 6:
            return False, "", 0.0
        atr    = self._calculate_atr(df)
        scope  = df.iloc[-(self.mss_lookback + n + 1):-n - 1]
        swing_h = scope["high"].max()
        swing_l = scope["low"].min()

        recent_window = df.iloc[-(n + 1):-1]
        sweep_high = recent_window["high"].max() > swing_h
        sweep_low  = recent_window["low"].min()  < swing_l
        curr_close = df["close"].iloc[-1]

        # BSL swept (above swing_h) → expect BEARISH CHoCH/BOS
        if sweep_high and curr_close < swing_h:
            found_mss, reason, score = self._detect_micro_choch(df)
            if not found_mss:
                found_mss, reason, score = self._detect_micro_bos(df)
            if found_mss and "Bearish" in reason:
                return True, f"BSL Sweep+MSS (swept {swing_h:.2f}): {reason}", min(1.0, score * 1.15)

        # SSL swept (below swing_l) → expect BULLISH CHoCH/BOS
        if sweep_low and curr_close > swing_l:
            found_mss, reason, score = self._detect_micro_choch(df)
            if not found_mss:
                found_mss, reason, score = self._detect_micro_bos(df)
            if found_mss and "Bullish" in reason:
                return True, f"SSL Sweep+MSS (swept {swing_l:.2f}): {reason}", min(1.0, score * 1.15)

        return False, "", 0.0

    def _detect_ibos(self, df) -> Tuple[bool, str, float]:
        short_lookback = max(5, self.mss_lookback // 2)
        if len(df) < short_lookback + 3:
            return False, "", 0.0
        scope      = df.iloc[-(short_lookback + 1):-1]
        mini_sh    = scope["high"].max()
        mini_sl    = scope["low"].min()
        last_close = df["close"].iloc[-1]
        if last_close > mini_sh:
            return True, f"Bullish iBOS: Close {last_close:.2f} > {mini_sh:.2f}", 0.65
        if last_close < mini_sl:
            return True, f"Bearish iBOS: Close {last_close:.2f} < {mini_sl:.2f}", 0.65
        return False, "", 0.0

    def _detect_fair_value_return(self, df) -> Tuple[bool, str, float]:
        """
        FVR: price in the 40–60 % equilibrium of a recent displacement leg.

        FIX: direction label now requires the candle body to confirm the
        inferred direction. A "bullish FVR" must have a bullish close (close > open)
        — without this a bearish rejection candle AT the FVR low would still label
        as bullish based purely on position within the zone.
        """
        if len(df) < self.mss_lookback + 4:
            return False, "", 0.0
        atr    = self._calculate_atr(df)
        scope  = df.iloc[-(self.mss_lookback + 1):-1]
        leg_h  = scope["high"].max()
        leg_l  = scope["low"].min()
        leg    = leg_h - leg_l
        if leg <= 0:
            return False, "", 0.0

        fvr_low  = leg_l + leg * self.FVR_RETRACE_LOW
        fvr_high = leg_l + leg * self.FVR_RETRACE_HIGH
        c        = df.iloc[-1]
        body     = abs(c["close"] - c["open"])
        rng      = c["high"] - c["low"]

        if fvr_low <= c["close"] <= fvr_high:
            wick_score = 1.0 - (body / rng) if rng > 0 else 0.0
            score      = min(0.75, 0.60 + wick_score * 0.15)

            # FIX: require candle direction to match the inferred FVR direction
            mid_zone  = (fvr_low + fvr_high) / 2
            if c["close"] > mid_zone and c["close"] > c["open"]:  # bullish FVR
                return True, f"Bullish Fair Value Return at {fvr_low:.2f}–{fvr_high:.2f}", score
            elif c["close"] <= mid_zone and c["close"] < c["open"]:  # bearish FVR
                return True, f"Bearish Fair Value Return at {fvr_low:.2f}–{fvr_high:.2f}", score

        return False, "", 0.0

    # ─────────────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────────────

    def _detect_mss(self, df) -> Tuple[bool, str, float]:
        """
        Priority order: Sweep+MSS > MicroMSS > MicroCHoCH > MicroBOS > iBOS > FVR.
        FIX: returns immediately on first match (was looping all then returning last).
        """
        for det in [
            self._detect_sweep_mss,
            self._detect_micro_mss,
            self._detect_micro_choch,
            self._detect_micro_bos,
            self._detect_ibos,
            self._detect_fair_value_return,
        ]:
            found, reason, score = det(df)
            if found:
                return found, reason, score
        last_close = df["close"].iloc[-1] if len(df) > 0 else 0
        return False, f"No micro structure — Close {last_close:.2f}", 0.0

    def _bias_from_reason(self, reason: str) -> str:
        r = reason.lower()
        if "bullish" in r:
            return "bullish"
        if "bearish" in r:
            return "bearish"
        return "neutral"

    def validate(self, df) -> Tuple[bool, float]:
        found, reason, score = self._detect_mss(df)
        self._reason = reason
        self._bias   = self._bias_from_reason(reason)
        return found, score

    def process(self, data: dict) -> dict:
        """
        Multi-TF micro structure detection: M15 > M5.
        FIX: 'bias' key now always included in result dict.
        """
        m15_candles = data.get("m15_candles", [])
        m5_candles  = data.get("m5_candles",  [])

        if m15_candles:
            df_m15 = pd.DataFrame(m15_candles)
            found, reason, score = self._detect_mss(df_m15)
            if found:
                self._reason = f"M15: {reason}"
                self._bias   = self._bias_from_reason(reason)
                return {"status": True,
                        "reason": f"MicroMSS: {self._reason}",
                        "score": score,
                        "bias": self._bias}

        if m5_candles:
            df_m5 = pd.DataFrame(m5_candles)
            found, reason, score = self._detect_mss(df_m5)
            self._reason = f"M5: {reason}" if found else f"No micro MSS on any TF — {reason}"
            self._bias   = self._bias_from_reason(reason) if found else "neutral"
            return {"status": found,
                    "reason": f"MicroMSS: {self._reason}",
                    "score": score,
                    "bias": self._bias}

        self._reason = "No candle data"
        self._bias   = "neutral"
        return {"status": False, "reason": f"MicroMSS: {self._reason}",
                "score": 0.0, "bias": "neutral"}
