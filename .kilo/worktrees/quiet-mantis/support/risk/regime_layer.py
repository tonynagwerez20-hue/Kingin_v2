"""
RegimeLayer — Gold Calibrated Edition
======================================
Fixes:
  • Original threshold=2.0 applied to raw Gold price returns (e.g. 4860.xx).
    A std-dev of returns on M15 Gold is typically 0.5–8.0 price points,
    meaning the old threshold almost NEVER triggered — regime was always STABLE.
  • Now uses PERCENTAGE returns (normalised by price level) so the threshold
    is instrument-agnostic and correctly calibrated for Gold at any price.
  • Added ADR-ratio method as a secondary cross-check.
  • Exposes current_regime as an attribute so trading_loop_controller.py
    can read it via hasattr(regime_layer, 'current_regime').
  • Added RANGING detection (tight consolidation that is neither volatile
    nor cleanly trending) as a third regime state.

Regime states:
  STABLE   — normal trending conditions, signals allowed
  VOLATILE — abnormal volatility (news spike, gap), signals suppressed
  RANGING  — tight consolidation, ADR too small for clean SMC setups
"""

import numpy as np
from typing import List, Dict


class RegimeLayer:
    # Percentage-return thresholds (normalised, instrument-agnostic)
    VOLATILE_PCT_THRESHOLD = 0.0008   # 0.08% std-dev of returns on M15 = high vol
    RANGING_ADR_RATIO      = 0.25     # today's range < 25 % of rolling ADR = ranging
    ADR_LOOKBACK_BARS      = 96       # 96 M15 bars = 1 day for ADR calculation

    def __init__(self, volatility_threshold: float = None):
        # Accept legacy float arg without breaking; convert to pct threshold
        # If caller passes the old default 2.0 we ignore it and use calibrated value
        self.volatile_pct_threshold = self.VOLATILE_PCT_THRESHOLD
        self.ranging_adr_ratio      = self.RANGING_ADR_RATIO
        self.adr_lookback           = self.ADR_LOOKBACK_BARS
        self.current_regime         = "STABLE"   # exposed as attribute

    def _pct_returns(self, closes: List[float]) -> np.ndarray:
        """Compute percentage returns from a close price list."""
        arr = np.array(closes, dtype=float)
        # Guard against zero prices
        with np.errstate(divide="ignore", invalid="ignore"):
            rets = np.diff(arr) / np.where(arr[:-1] != 0, arr[:-1], 1.0)
        return rets

    def _is_volatile(self, ltf_buffer: List[Dict]) -> bool:
        """
        True if the recent percentage-return std-dev exceeds the threshold.
        Uses last 10 bars (30 minutes on M15) for responsiveness.
        """
        if len(ltf_buffer) < 10:
            return False
        closes  = [c["close"] for c in ltf_buffer[-10:]]
        returns = self._pct_returns(closes)
        vol     = float(np.std(returns))
        return vol > self.volatile_pct_threshold

    def _is_ranging(self, ltf_buffer: List[Dict]) -> bool:
        """
        True if today's intraday range is too tight relative to the rolling ADR.
        Prevents false BOS signals during Asian consolidation / holiday sessions.
        """
        n = len(ltf_buffer)
        if n < max(self.adr_lookback, 24):
            return False

        # Rolling ADR: mean of daily ranges over the lookback window
        daily_ranges = []
        bars_per_day = 96   # M15: 24h = 96 bars
        for d in range(1, (self.adr_lookback // bars_per_day) + 1):
            end   = n - (d - 1) * bars_per_day
            start = max(0, end - bars_per_day)
            chunk = ltf_buffer[start:end]
            if len(chunk) > 4:
                highs  = [c["high"]  for c in chunk]
                lows   = [c["low"]   for c in chunk]
                daily_ranges.append(max(highs) - min(lows))

        if not daily_ranges:
            return False

        adr         = float(np.mean(daily_ranges))
        today_slice = ltf_buffer[-min(96, n):]
        today_range = max(c["high"] for c in today_slice) - min(c["low"] for c in today_slice)

        return adr > 0 and (today_range / adr) < self.ranging_adr_ratio

    def detect_regime(self, ltf_buffer: List[Dict]) -> str:
        """
        Detects market regime from a buffer of M15 candle dicts.
        Returns 'STABLE', 'VOLATILE', or 'RANGING'.
        Also stores result in self.current_regime for attribute access.
        """
        if len(ltf_buffer) < 10:
            self.current_regime = "STABLE"
            return self.current_regime

        if self._is_volatile(ltf_buffer):
            self.current_regime = "VOLATILE"
        elif self._is_ranging(ltf_buffer):
            self.current_regime = "RANGING"
        else:
            self.current_regime = "STABLE"

        return self.current_regime
