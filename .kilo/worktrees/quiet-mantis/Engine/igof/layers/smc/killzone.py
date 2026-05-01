"""
KillzoneFilterLayer — Gold SMC Edition
=======================================================
Time-of-day session filter calibrated specifically for Gold (XAUUSD):

  SESSION TIERS (scored highest → lowest)
  ─────────────────────────────────────────
  1. London–NY Overlap  13:00–16:00 GMT   Score 1.00  (peak Gold volatility)
  2. London Open        07:00–09:00 GMT   Score 0.90  (Judas swing window)
  3. NY Open            13:30–15:00 GMT   Score 0.90  (NY silver bullet)
  4. London Session     09:00–16:00 GMT   Score 0.80
  5. NY Session         13:00–17:00 GMT   Score 0.80
  6. Gold Macro Window  08:30–10:00 GMT   Score 0.85  (NFP/CPI/FOMC releases)
  7. Asian consolidation00:00–07:00 GMT   Score 0.40  (range-building, avoid trading)

  BLOCKED WINDOWS (score 0.0, always reject)
  ───────────────────────────────────────────
  • Dead zone: 20:00–23:00 GMT (Asian pre-session, wide spreads)
  • Daily close: 23:00–00:00 GMT (NY close, thin liquidity)

  ICT SILVER BULLET WINDOWS
  ──────────────────────────
  • 02:00–04:00 GMT  (Asian Silver Bullet)
  • 10:00–11:00 GMT  (London Silver Bullet)
  • 14:00–15:00 GMT  (NY Silver Bullet)
"""

from datetime import time, datetime, timezone
from typing import Tuple
import pandas as pd
from .base import SMCLayerBase
import logging

logger = logging.getLogger("KillzoneFilter")


class KillzoneFilterLayer(SMCLayerBase):
    # ── Session boundaries (UTC/GMT) ──────────────────────────────────
    LONDON_OPEN_UTC        = time(7,  0)
    LONDON_OPEN_END_UTC    = time(9,  0)   # London open killzone
    LONDON_CLOSE_UTC       = time(16, 0)
    NY_OPEN_UTC            = time(13, 30)
    NY_OPEN_END_UTC        = time(15, 0)   # NY open killzone
    NY_CLOSE_UTC           = time(17, 0)
    OVERLAP_START_UTC      = time(13, 0)
    OVERLAP_END_UTC        = time(16, 0)
    ASIAN_START_UTC        = time(0,  0)
    ASIAN_END_UTC          = time(7,  0)
    MACRO_START_UTC        = time(8,  30)
    MACRO_END_UTC          = time(10, 0)
    DEAD_ZONE_START        = time(20, 0)
    DEAD_ZONE_END          = time(23, 0)
    DAILY_CLOSE_START      = time(23, 0)

    # Silver Bullet windows
    SB_ASIAN_START         = time(2,  0)
    SB_ASIAN_END           = time(4,  0)
    SB_LONDON_START        = time(10, 0)
    SB_LONDON_END          = time(11, 0)
    SB_NY_START            = time(14, 0)
    SB_NY_END              = time(15, 0)

    def __init__(self, name="KillzoneFilter", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason = "Killzone not yet evaluated"
        # Allow overrides from config
        self.london_start   = self.config.get("london_start",   self.LONDON_OPEN_UTC)
        self.london_end     = self.config.get("london_end",     self.LONDON_CLOSE_UTC)
        self.ny_start       = self.config.get("ny_start",       self.NY_OPEN_UTC)
        self.ny_end         = self.config.get("ny_end",         self.NY_CLOSE_UTC)
        self.overlap_start  = self.config.get("overlap_start",  self.OVERLAP_START_UTC)
        self.overlap_end    = self.config.get("overlap_end",    self.OVERLAP_END_UTC)
        self.allow_asian    = self.config.get("allow_asian",    False)

    # ══════════════════════════════════════════════════════════════════
    # Time conversion
    # ══════════════════════════════════════════════════════════════════

    def _get_utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_london_time(self, utc_dt: datetime) -> datetime:
        try:
            from zoneinfo import ZoneInfo
            return utc_dt.astimezone(ZoneInfo("Europe/London"))
        except ImportError:
            year = utc_dt.year
            march31 = datetime(year, 3, 31, 12, 0, tzinfo=timezone.utc)
            days_to_sunday = (march31.weekday() + 1) % 7
            bst_start = datetime(year, 3, 31 - days_to_sunday, 1, 0, tzinfo=timezone.utc)
            oct31 = datetime(year, 10, 31, 12, 0, tzinfo=timezone.utc)
            days_to_sunday = (oct31.weekday() + 1) % 7
            gmt_start = datetime(year, 10, 31 - days_to_sunday, 1, 0, tzinfo=timezone.utc)
            offset = 1 if bst_start <= utc_dt < gmt_start else 0
            new_hour = (utc_dt.hour + offset) % 24
            return utc_dt.replace(tzinfo=None).replace(hour=new_hour)

    def _get_ny_time(self, utc_dt: datetime) -> datetime:
        try:
            from zoneinfo import ZoneInfo
            return utc_dt.astimezone(ZoneInfo("America/New_York"))
        except ImportError:
            year = utc_dt.year
            march1_wd = datetime(year, 3, 1, 12, 0, tzinfo=timezone.utc).weekday()
            first_sun = (7 - march1_wd) % 7 or 7
            edt_start = datetime(year, 3, first_sun + 7, 2, 0, tzinfo=timezone.utc)
            nov1_wd   = datetime(year, 11, 1, 12, 0, tzinfo=timezone.utc).weekday()
            first_sun_nov = (7 - nov1_wd) % 7 or 7
            est_start = datetime(year, 11, first_sun_nov, 2, 0, tzinfo=timezone.utc)
            offset    = -4 if edt_start <= utc_dt < est_start else -5
            new_hour  = (utc_dt.hour + offset) % 24
            return utc_dt.replace(tzinfo=None).replace(hour=new_hour)

    # ══════════════════════════════════════════════════════════════════
    # Session checks
    # ══════════════════════════════════════════════════════════════════

    def _is_in_window(self, t: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= t < end
        # Overnight wrap
        return t >= start or t < end

    def _is_dead_zone(self, utc_time: time) -> bool:
        """Dead zone: 20:00–00:00 GMT — avoid Gold due to wide spreads & thin liquidity."""
        return self._is_in_window(utc_time, self.DEAD_ZONE_START, time(0, 0))

    def _is_silver_bullet(self, utc_time: time) -> Tuple[bool, str]:
        """ICT Silver Bullet windows — highest probability micro-windows."""
        if self._is_in_window(utc_time, self.SB_ASIAN_START, self.SB_ASIAN_END):
            return True, f"Asian Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"
        if self._is_in_window(utc_time, self.SB_LONDON_START, self.SB_LONDON_END):
            return True, f"London Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"
        if self._is_in_window(utc_time, self.SB_NY_START, self.SB_NY_END):
            return True, f"NY Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"
        return False, ""

    def _get_session_score(self, utc_now: datetime) -> Tuple[bool, float, str]:
        """
        Determine the session tier and score for the current UTC time.
        Returns (status, score, reason).
        """
        utc_time   = utc_now.time()
        london_dt  = self._get_london_time(utc_now)
        ny_dt      = self._get_ny_time(utc_now)
        london_t   = london_dt.time()
        ny_t       = ny_dt.time()

        # ── Blocked windows (always reject) ───────────────────────────
        if self._is_dead_zone(utc_time):
            return False, 0.0, f"Dead zone — wide spreads ({utc_time.strftime('%H:%M')} GMT)"

        # ── Tier 1: London–NY Overlap ─────────────────────────────────
        if self._is_in_window(utc_time, self.OVERLAP_START_UTC, self.OVERLAP_END_UTC):
            # Silver Bullet check within overlap (extra high conviction)
            sb, sb_reason = self._is_silver_bullet(utc_time)
            if sb:
                return True, 1.00, f"NY Silver Bullet within Overlap — {sb_reason}"
            return True, 1.00, f"London–NY Overlap Active ({utc_time.strftime('%H:%M')} GMT)"

        # ── Tier 2: London Open Killzone (07:00–09:00 London) ─────────
        if self._is_in_window(london_t, self.LONDON_OPEN_UTC, self.LONDON_OPEN_END_UTC):
            return True, 0.90, f"London Open Killzone ({london_t.strftime('%H:%M')} London)"

        # ── Tier 3: NY Open Killzone (13:30–15:00 UTC) ─────────────────
        if self._is_in_window(utc_time, self.NY_OPEN_UTC, self.NY_OPEN_END_UTC):
            sb, sb_reason = self._is_silver_bullet(utc_time)
            if sb:
                return True, 0.95, f"NY Open + Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"
            return True, 0.90, f"NY Open Killzone ({utc_time.strftime('%H:%M')} GMT)"

        # ── Tier 4: Gold Macro Window (08:30–10:00 UTC) ────────────────
        if self._is_in_window(utc_time, self.MACRO_START_UTC, self.MACRO_END_UTC):
            return True, 0.85, f"Gold Macro Window ({utc_time.strftime('%H:%M')} GMT)"

        # ── Tier 5: London Silver Bullet (10:00–11:00 UTC) ─────────────
        if self._is_in_window(utc_time, self.SB_LONDON_START, self.SB_LONDON_END):
            return True, 0.85, f"London Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"

        # ── Tier 6: London Session (active) ──────────────────────────
        if self._is_in_window(london_t, self.LONDON_OPEN_UTC, self.LONDON_CLOSE_UTC):
            return True, 0.80, f"London Session Active ({london_t.strftime('%H:%M')} London)"

        # ── Tier 7: NY Session (active) ───────────────────────────────
        if self._is_in_window(ny_t, time(8, 0), self.NY_CLOSE_UTC):
            return True, 0.80, f"NY Session Active ({ny_t.strftime('%H:%M')} NY)"

        # ── Tier 8: Asian Silver Bullet ──────────────────────────────
        if self._is_in_window(utc_time, self.SB_ASIAN_START, self.SB_ASIAN_END):
            if self.allow_asian:
                return True, 0.60, f"Asian Silver Bullet ({utc_time.strftime('%H:%M')} GMT)"
            return False, 0.0, f"Asian Silver Bullet — disabled (allow_asian=False)"

        # ── Tier 9: Asian Session ─────────────────────────────────────
        if self._is_in_window(utc_time, self.ASIAN_START_UTC, self.ASIAN_END_UTC):
            if self.allow_asian:
                return True, 0.40, f"Asian Session ({utc_time.strftime('%H:%M')} GMT)"
            return False, 0.0, f"Asian Session — range building, not trading"

        return False, 0.0, f"Outside all sessions (London: {london_t.strftime('%H:%M')}, NY: {ny_t.strftime('%H:%M')})"

    def _get_session_info(self, utc_now: datetime) -> dict:
        london_dt = self._get_london_time(utc_now)
        ny_dt     = self._get_ny_time(utc_now)
        utc_t     = utc_now.time()
        london_t  = london_dt.time()
        ny_t      = ny_dt.time()
        return {
            "overlap":       self._is_in_window(utc_t, self.OVERLAP_START_UTC, self.OVERLAP_END_UTC),
            "london":        self._is_in_window(london_t, self.LONDON_OPEN_UTC, self.LONDON_CLOSE_UTC),
            "ny":            self._is_in_window(ny_t, time(8, 0), self.NY_CLOSE_UTC),
            "london_open_kz":self._is_in_window(london_t, self.LONDON_OPEN_UTC, self.LONDON_OPEN_END_UTC),
            "ny_open_kz":    self._is_in_window(utc_t, self.NY_OPEN_UTC, self.NY_OPEN_END_UTC),
            "silver_bullet": self._is_silver_bullet(utc_t)[0],
            "dead_zone":     self._is_dead_zone(utc_t),
            "london_time":   london_t.strftime("%H:%M"),
            "ny_time":       ny_t.strftime("%H:%M"),
            "utc_time":      utc_t.strftime("%H:%M"),
        }

    # ══════════════════════════════════════════════════════════════════
    # Orchestration (signatures unchanged)
    # ══════════════════════════════════════════════════════════════════

    def validate(self, df) -> Tuple[bool, float]:
        if df is None or (hasattr(df, 'empty') and df.empty):
            return False, 0.0
        utc_now = self._get_utc_now()
        status, score, reason = self._get_session_score(utc_now)
        self._reason = reason
        return status, score

    def process(self, data: dict) -> dict:
        utc_now = self._get_utc_now()
        status, score, reason = self._get_session_score(utc_now)
        self._reason = reason
        session_info = self._get_session_info(utc_now)
        return {
            "status":       status,
            "reason":       f"KillzoneFilter: {reason}",
            "score":        score,
            "session_info": session_info,
        }
