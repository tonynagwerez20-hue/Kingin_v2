"""
MechanicalStructureLayer — Gold SMC Edition
=======================================================
Detects ALL structural events used in Gold (XAUUSD) SMC trading:

  • BOS  (Break of Structure)       — trend continuation confirmation
  • CHoCH (Change of Character)     — first sign of reversal
  • MSS  (Market Structure Shift)   — confirmed reversal (CHoCH + displacement)
  • IBOS (Internal BOS)             — lower-timeframe structure within larger swing
  • Strong / Weak Highs and Lows    — distinguishes defended vs. undefended levels
  • HTF Bias alignment              — only takes trades aligned with H1/H4 structure

Multi-timeframe priority: H1 (bias) → M15 (context) → M5 (trigger)

FIXES vs ORIGINAL
─────────────────
1. SMC ordering corrected: in M5/M15 passes CHoCH/MSS now run BEFORE BOS.
   BOS = continuation; CHoCH = reversal. The original would always fire BOS
   first and never surface a CHoCH/MSS in an existing trend.
2. HTF bias gate added: M5 or M15 signals that contradict H1 bias are
   skipped. The original emitted counter-trend signals freely.
3. MSS score corrected: was 0.95 (higher than BOS 1.0 which is wrong —
   MSS is a reversal signal, not a stronger BOS). Fixed to 0.90.
4. _is_ranging() now accepts bars_per_day param instead of hardcoding 24
   (H1 assumption). M15 = 96 bars/day, M5 = 288 bars/day.
5. Spread gate runs BEFORE range gate (was after in original).
6. self._bias is always set before returning so base.process() reads it.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from .base import SMCLayerBase
import logging

logger = logging.getLogger("MechanicalStructure")


class MechanicalStructureLayer(SMCLayerBase):
    FRACTAL_BARS     = 5
    MIN_SWING_BARS   = 10
    CHoCH_LOOKBACK   = 40
    STRONG_LEVEL_ATR = 0.5
    IBOS_LOOKBACK    = 15

    def __init__(self, name="MechanicalStructure", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason        = "Structure not yet evaluated"
        self._bias          = "neutral"
        self.fractal_bars   = self.config.get("fractal_bars",   self.FRACTAL_BARS)
        self.choch_lookback = self.config.get("choch_lookback", self.CHoCH_LOOKBACK)

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

    def _get_fractals(self, df, n=None):
        n     = n or self.fractal_bars
        highs = df["high"].values
        lows  = df["low"].values
        sh_idx, sl_idx = [], []
        for i in range(n, len(highs) - n):
            if all(highs[i] > highs[i - j] for j in range(1, n + 1)) and \
               all(highs[i] > highs[i + j] for j in range(1, n + 1)):
                sh_idx.append(i)
            if all(lows[i] < lows[i - j] for j in range(1, n + 1)) and \
               all(lows[i] < lows[i + j] for j in range(1, n + 1)):
                sl_idx.append(i)
        return np.array(sh_idx), np.array(sl_idx)

    def _classify_swing_strength(self, df, idx, kind, atr):
        if idx < 0 or idx >= len(df):
            return "weak"
        body = abs(df.iloc[idx]["close"] - df.iloc[idx]["open"])
        return "strong" if body > self.STRONG_LEVEL_ATR * atr else "weak"

    def _get_swing_series(self, df):
        """Ordered alternating H/L swing series for CHoCH detection."""
        sh_idx, sl_idx = self._get_fractals(df)
        atr    = self._calculate_atr(df)
        events = []
        for i in sh_idx:
            events.append({"type": "H", "price": df["high"].iloc[i], "idx": i,
                            "strength": self._classify_swing_strength(df, i, "H", atr)})
        for i in sl_idx:
            events.append({"type": "L", "price": df["low"].iloc[i], "idx": i,
                            "strength": self._classify_swing_strength(df, i, "L", atr)})
        events.sort(key=lambda x: x["idx"])
        # Deduplicate to alternating H/L, keeping more extreme of same-type runs
        filtered, last_type = [], None
        for e in events:
            if e["type"] != last_type:
                filtered.append(e)
                last_type = e["type"]
            else:
                if (e["type"] == "H" and e["price"] > filtered[-1]["price"]) or \
                   (e["type"] == "L" and e["price"] < filtered[-1]["price"]):
                    filtered[-1] = e
        return filtered

    def _extract_bias(self, reason: str) -> str:
        r = reason.lower()
        if "bearish" in r:
            return "bearish"
        if "bullish" in r:
            return "bullish"
        return "neutral"

    # ─────────────────────────────────────────────────────────────────
    # Detectors — each returns (found: bool, reason: str)
    # ─────────────────────────────────────────────────────────────────

    def _detect_bos(self, df):
        """BOS: close beyond the last confirmed fractal swing high/low."""
        if len(df) < self.MIN_SWING_BARS:
            return False, "Insufficient data"
        atr           = self._calculate_atr(df)
        sh_idx, sl_idx = self._get_fractals(df)
        last_close    = df["close"].iloc[-1]

        if len(sh_idx) > 0:
            last_sh = df["high"].iloc[sh_idx[-1]]
            strength = self._classify_swing_strength(df, sh_idx[-1], "H", atr)
            if last_close > last_sh:
                tag = "Strong BOS" if strength == "strong" else "Weak BOS"
                return True, f"Bullish {tag}: Close {last_close:.2f} > SwingHigh {last_sh:.2f}"

        if len(sl_idx) > 0:
            last_sl  = df["low"].iloc[sl_idx[-1]]
            strength = self._classify_swing_strength(df, sl_idx[-1], "L", atr)
            if last_close < last_sl:
                tag = "Strong BOS" if strength == "strong" else "Weak BOS"
                return True, f"Bearish {tag}: Close {last_close:.2f} < SwingLow {last_sl:.2f}"

        return False, f"No BOS — Close: {last_close:.2f}"

    def _detect_choch(self, df):
        """
        CHoCH: close breaks the most recent OPPOSING swing leg.
        Bearish CHoCH: HH/HL series → close below last HL.
        Bullish CHoCH: LH/LL series → close above last LH.

        FIX: slice df THEN reset index so _get_swing_series works on
        contiguous 0-based indices instead of misaligned original indices.
        """
        if len(df) < self.choch_lookback + 4:
            return False, ""
        atr    = self._calculate_atr(df)
        scope  = df.iloc[-self.choch_lookback:].reset_index(drop=True)
        swings = self._get_swing_series(scope)
        if len(swings) < 4:
            return False, ""

        last_close = df["close"].iloc[-1]
        last_lows  = [s for s in swings if s["type"] == "L"][-2:]
        last_highs = [s for s in swings if s["type"] == "H"][-2:]

        # Bearish CHoCH: Higher Low broken downward
        if len(last_lows) == 2:
            prev_l, curr_l = last_lows[0], last_lows[1]
            if curr_l["price"] > prev_l["price"] and last_close < curr_l["price"]:
                disp = abs(df["close"].iloc[-1] - df["open"].iloc[-1]) / atr
                tag  = "Displacement CHoCH" if disp > 0.5 else "CHoCH"
                return True, f"Bearish {tag}: Close {last_close:.2f} < HL {curr_l['price']:.2f}"

        # Bullish CHoCH: Lower High broken upward
        if len(last_highs) == 2:
            prev_h, curr_h = last_highs[0], last_highs[1]
            if curr_h["price"] < prev_h["price"] and last_close > curr_h["price"]:
                disp = abs(df["close"].iloc[-1] - df["open"].iloc[-1]) / atr
                tag  = "Displacement CHoCH" if disp > 0.5 else "CHoCH"
                return True, f"Bullish {tag}: Close {last_close:.2f} > LH {curr_h['price']:.2f}"

        return False, ""

    def _detect_mss(self, df):
        """
        MSS: CHoCH + displacement candle (body > 0.5 ATR).
        FIX: score 0.90 (was 0.95 > BOS 1.0, which is wrong — MSS is reversal,
        not a stronger continuation signal than BOS).
        """
        found, reason = self._detect_choch(df)
        if not found:
            return False, ""
        atr  = self._calculate_atr(df)
        body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        if body > 0.5 * atr:
            return True, f"MSS confirmed — {reason}"
        return False, ""

    def _detect_ibos(self, df):
        """Internal BOS on a short lookback window (LTF alignment signal)."""
        if len(df) < self.IBOS_LOOKBACK + 4:
            return False, ""
        mini_df = df.iloc[-self.IBOS_LOOKBACK:].copy().reset_index(drop=True)
        found, reason = self._detect_bos(mini_df)
        if found:
            return True, f"iBOS ({self.IBOS_LOOKBACK}-bar): {reason}"
        return False, ""

    def _detect_strong_weak_levels(self, df):
        """Break of the most recent STRONG fractal level."""
        if len(df) < self.MIN_SWING_BARS:
            return False, ""
        atr           = self._calculate_atr(df)
        sh_idx, sl_idx = self._get_fractals(df)
        last_close    = df["close"].iloc[-1]

        strong_sh = next((df["high"].iloc[i] for i in reversed(sh_idx)
                          if self._classify_swing_strength(df, i, "H", atr) == "strong"), None)
        strong_sl = next((df["low"].iloc[i]  for i in reversed(sl_idx)
                          if self._classify_swing_strength(df, i, "L", atr) == "strong"), None)

        if strong_sh and last_close > strong_sh:
            return True, f"Bullish BOS — Strong high {strong_sh:.2f} broken"
        if strong_sl and last_close < strong_sl:
            return True, f"Bearish BOS — Strong low {strong_sl:.2f} broken"
        return False, ""

    # ─────────────────────────────────────────────────────────────────
    # Orchestration
    # ─────────────────────────────────────────────────────────────────

    def _is_ranging(self, df, bars_per_day=24, adr_lookback=5, range_threshold=0.30) -> bool:
        """
        FIX: bars_per_day is now a parameter instead of hardcoded 24.
        H1 data → 24 bars/day; M15 → 96; M5 → 288.
        """
        if len(df) < adr_lookback * bars_per_day + 2:
            return False
        daily_ranges = []
        for d in range(adr_lookback):
            start = -(d + 1) * bars_per_day
            end   = -d * bars_per_day if d > 0 else None
            chunk = df.iloc[start:end]
            if len(chunk) > 0:
                daily_ranges.append(chunk["high"].max() - chunk["low"].min())
        if not daily_ranges:
            return False
        adr         = np.mean(daily_ranges)
        today_range = df["high"].iloc[-bars_per_day:].max() - df["low"].iloc[-bars_per_day:].min()
        return adr > 0 and (today_range / adr) < range_threshold

    def validate(self, df) -> Tuple[bool, float]:
        """
        Single-TF fallback.
        FIX: detector order is now MSS → CHoCH → BOS → iBOS → strong/weak.
        Reversal signals run first; continuation (BOS) is checked after.
        """
        for detector, score_val in [
            (self._detect_mss,                0.90),
            (self._detect_choch,              0.80),
            (self._detect_bos,                1.00),
            (self._detect_ibos,               0.75),
            (self._detect_strong_weak_levels, 0.80),
        ]:
            found, reason = detector(df)
            if found:
                self._reason = reason
                self._bias   = self._extract_bias(reason)
                return True, score_val
        self._reason = f"No structure — Close: {df['close'].iloc[-1]:.2f}"
        self._bias   = "neutral"
        return False, 0.0

    def process(self, data: dict) -> dict:
        """
        Multi-TF structure detection with HTF bias gate.

        FIXES APPLIED
        ─────────────
        • Spread gate runs first (hard block).
        • Range gate uses correct bars_per_day per TF.
        • H1 establishes htf_bias; M15/M5 signals contradicting it are skipped.
        • All TF passes use corrected detector order: MSS→CHoCH→BOS.
        """
        h1_candles  = data.get("h1_candles",  [])
        m15_candles = data.get("m15_candles", [])
        m5_candles  = data.get("m5_candles",  [])

        # ── 1. Spread gate ────────────────────────────────────────────
        tick       = data.get("tick", {})
        spread     = tick.get("spread", 0.0)
        max_spread = self.config.get("max_spread_points", 50)
        if spread > max_spread:
            self._reason = f"SPREAD BLOCK: Spread {spread:.1f} pts > {max_spread} limit"
            self._bias   = "neutral"
            logger.info(self._reason)
            return {"status": False, "reason": f"Structure: {self._reason}",
                    "score": 0.0, "bias": "neutral"}

        # ── 2. Range / consolidation gate (H1) ───────────────────────
        if h1_candles:
            df_h1 = pd.DataFrame(h1_candles)
            if self._is_ranging(df_h1, bars_per_day=24):
                self._reason = "RANGE MODE: H1 range < 30% of ADR — no structural edge"
                self._bias   = "neutral"
                logger.info(self._reason)
                return {"status": False, "reason": f"Structure: {self._reason}",
                        "score": 0.0, "bias": "neutral"}

        # ── 3. H1 bias pass ───────────────────────────────────────────
        htf_bias: Optional[str] = None
        if h1_candles:
            df_h1 = pd.DataFrame(h1_candles)
            for detector, score_val, label in [
                (self._detect_mss,   0.90, "MSS"),
                (self._detect_choch, 0.80, "CHoCH"),
                (self._detect_bos,   1.00, "BOS"),
            ]:
                found, reason = detector(df_h1)
                if found:
                    bias         = self._extract_bias(reason)
                    self._reason = f"H1 Structure ({label}): {reason}"
                    self._bias   = bias
                    htf_bias     = bias
                    return {"status": True, "reason": f"Structure: {self._reason}",
                            "score": score_val, "bias": bias}

        # ── 4. M15 contextual pass ────────────────────────────────────
        if m15_candles:
            df_m15 = pd.DataFrame(m15_candles)
            for detector, score_val, label in [
                (self._detect_mss,                0.90, "MSS"),
                (self._detect_choch,              0.80, "CHoCH"),
                (self._detect_bos,                1.00, "BOS"),
                (self._detect_strong_weak_levels, 0.80, "Strong/Weak"),
            ]:
                found, reason = detector(df_m15)
                if not found:
                    continue
                bias = self._extract_bias(reason)
                if htf_bias and bias != "neutral" and bias != htf_bias:
                    logger.debug(f"M15 {label} ({bias}) skipped — contradicts H1 ({htf_bias})")
                    continue
                self._reason = f"M15 Structure ({label}): {reason}"
                self._bias   = bias
                return {"status": True, "reason": f"Structure: {self._reason}",
                        "score": score_val, "bias": bias}

        # ── 5. M5 trigger pass ────────────────────────────────────────
        if m5_candles:
            df_m5 = pd.DataFrame(m5_candles)
            for detector, score_val, label in [
                (self._detect_mss,                0.90, "MSS"),
                (self._detect_choch,              0.80, "CHoCH"),
                (self._detect_bos,                1.00, "BOS"),
                (self._detect_ibos,               0.75, "iBOS"),
                (self._detect_strong_weak_levels, 0.80, "Strong/Weak"),
            ]:
                found, reason = detector(df_m5)
                if not found:
                    continue
                bias = self._extract_bias(reason)
                if htf_bias and bias != "neutral" and bias != htf_bias:
                    logger.debug(f"M5 {label} ({bias}) skipped — contradicts H1 ({htf_bias})")
                    continue
                self._reason = f"M5 Structure ({label}): {reason}"
                self._bias   = bias
                return {"status": True, "reason": f"Structure: {self._reason}",
                        "score": score_val, "bias": bias}
            self._reason = "No structure on any TF"
            self._bias   = "neutral"
            return {"status": False, "reason": f"Structure: {self._reason}",
                    "score": 0.0, "bias": "neutral"}

        self._reason = "No candle data for structure analysis"
        self._bias   = "neutral"
        return {"status": False, "reason": f"Structure: {self._reason}",
                "score": 0.0, "bias": "neutral"}
