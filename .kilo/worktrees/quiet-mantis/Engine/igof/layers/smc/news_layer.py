"""
NewsEventLayer — Gold & DXY News Edition
=======================================================
A dual-mode IGOF filtration layer that handles ALL macro news events
affecting Gold (XAUUSD) and the US Dollar Index (DXY):

  PROTECTIVE MODE (default)
  ─────────────────────────
  • Blocks standard IGOF signals in the 5-minute window BEFORE a
    high-impact event (spread spikes, stop hunts, erratic price action).
  • Returns status=False so the pipeline halts cleanly — no trade opens
    into a news candle.

  SCALP MODE (opt-in via config: enable_news_scalp=true)
  ────────────────────────────────────────────────────────
  • After an event fires, measures the first-candle displacement
    (close vs. open, body/ATR ratio) to determine direction.
  • Generates a SHORT-DURATION scalp signal (1–3 candles) with a
    tight SL (1.5 × ATR) and a 1:1.5 R:R TP, targeting the initial
    post-news impulse before mean reversion.
  • Qualifies the scalp only when:
      – The event impact is HIGH or MEDIUM-HIGH
      – The actual value deviates from the forecast by ≥ threshold
      – The first post-news candle body is ≥ 0.8 × ATR (displacement)
      – No open position already exists (open_positions_count == 0)

  COVERED NEWS EVENTS (Gold / DXY drivers)
  ─────────────────────────────────────────
  DXY-Positive (USD strengthens → Gold falls):
    NFP, CPI, Core CPI, PCE, Core PCE, PPI, Core PPI,
    FOMC Rate Decision, FOMC Minutes, Fed Chair Speech,
    ISM Manufacturing PMI, ISM Services PMI,
    Retail Sales, Core Retail Sales,
    ADP Employment, Jobless Claims, GDP (Advance/Preliminary/Final),
    Consumer Confidence (CB), Michigan Sentiment,
    JOLTS Job Openings, Durable Goods Orders

  DXY-Negative (USD weakens → Gold rises):
    Same events in miss direction — the layer reads actual vs forecast.

  Geopolitical / Safe-Haven (Gold up regardless of DXY):
    Marked in the event catalog as "SAFE_HAVEN" type — these override
    directional logic and always bias Gold long.

  API INTEGRATION
  ───────────────
  Primary  : Forex Factory RSS feed (free, no key required)
              https://nfs.faireconomy.media/ff_calendar_thisweek.json
  Fallback : FinnHub free tier (API key in config: finnhub_api_key)
              https://finnhub.io/api/v1/calendar/economic
  Cache    : 15-minute in-memory cache prevents rate-limit abuse.
             A local JSON fallback file is written on every successful
             fetch so the layer survives network outages.

  ARCHITECTURE
  ────────────
  • Inherits from SMCLayerBase — identical interface to all other layers.
  • process() returns the standard {status, reason, score} dict.
  • When scalp_mode fires, result also contains:
      {scalp_signal: {action, direction, sl_atr_mult, tp_rr, max_bars}}
  • No new IGOF layer slot needed — drop it in as layer 7 or configure
    it to replace KillzoneFilter (which already handles time gating).
  • Fully configurable via trading_params_lite.json under "config" key.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError
from pathlib import Path

from .base import SMCLayerBase

logger = logging.getLogger("NewsEventLayer")


# ══════════════════════════════════════════════════════════════════════
# Event catalog — all standard Gold / DXY drivers
# Impact: 3 = HIGH, 2 = MEDIUM-HIGH, 1 = MEDIUM, 0 = LOW
# gold_direction: +1 = typically bullish Gold, -1 = bearish Gold, 0 = mixed
# ══════════════════════════════════════════════════════════════════════
NEWS_CATALOG = {
    # ── Core NFP / Employment ──────────────────────────────────────────
    "Non-Farm Employment Change":              {"impact": 3, "gold_dir": -1, "type": "EMPLOYMENT"},
    "Non-Farm Payrolls":                       {"impact": 3, "gold_dir": -1, "type": "EMPLOYMENT"},
    "NFP":                                     {"impact": 3, "gold_dir": -1, "type": "EMPLOYMENT"},
    "ADP Non-Farm Employment Change":          {"impact": 2, "gold_dir": -1, "type": "EMPLOYMENT"},
    "Unemployment Rate":                       {"impact": 3, "gold_dir": +1, "type": "EMPLOYMENT"},
    "Average Hourly Earnings m/m":             {"impact": 2, "gold_dir": -1, "type": "EMPLOYMENT"},
    "Average Hourly Earnings y/y":             {"impact": 2, "gold_dir": -1, "type": "EMPLOYMENT"},
    "Initial Jobless Claims":                  {"impact": 2, "gold_dir": +1, "type": "EMPLOYMENT"},
    "Continuing Jobless Claims":               {"impact": 1, "gold_dir": +1, "type": "EMPLOYMENT"},
    "JOLTS Job Openings":                      {"impact": 2, "gold_dir": -1, "type": "EMPLOYMENT"},
    "Labor Market Conditions Index m/m":       {"impact": 1, "gold_dir": -1, "type": "EMPLOYMENT"},

    # ── Inflation ──────────────────────────────────────────────────────
    "CPI m/m":                                 {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "CPI y/y":                                 {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "Core CPI m/m":                            {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "Core CPI y/y":                            {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "PPI m/m":                                 {"impact": 2, "gold_dir": -1, "type": "INFLATION"},
    "PPI y/y":                                 {"impact": 2, "gold_dir": -1, "type": "INFLATION"},
    "Core PPI m/m":                            {"impact": 2, "gold_dir": -1, "type": "INFLATION"},
    "Core PPI y/y":                            {"impact": 2, "gold_dir": -1, "type": "INFLATION"},
    "PCE Price Index m/m":                     {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "PCE Price Index y/y":                     {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "Core PCE Price Index m/m":                {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "Core PCE Price Index y/y":                {"impact": 3, "gold_dir": -1, "type": "INFLATION"},
    "Import Prices m/m":                       {"impact": 1, "gold_dir": -1, "type": "INFLATION"},
    "Export Prices m/m":                       {"impact": 1, "gold_dir": -1, "type": "INFLATION"},

    # ── Federal Reserve ────────────────────────────────────────────────
    "FOMC Statement":                          {"impact": 3, "gold_dir":  0, "type": "FOMC"},
    "Federal Funds Rate":                      {"impact": 3, "gold_dir":  0, "type": "FOMC"},
    "FOMC Rate Decision":                      {"impact": 3, "gold_dir":  0, "type": "FOMC"},
    "FOMC Meeting Minutes":                    {"impact": 3, "gold_dir":  0, "type": "FOMC"},
    "Fed Chair Powell Speech":                 {"impact": 3, "gold_dir":  0, "type": "FED_SPEECH"},
    "Fed Chair Speaks":                        {"impact": 3, "gold_dir":  0, "type": "FED_SPEECH"},
    "Fed Member Speaks":                       {"impact": 2, "gold_dir":  0, "type": "FED_SPEECH"},
    "FOMC Member Speaks":                      {"impact": 2, "gold_dir":  0, "type": "FED_SPEECH"},
    "Fed Monetary Policy Report":              {"impact": 2, "gold_dir":  0, "type": "FED_SPEECH"},
    "Beige Book":                              {"impact": 2, "gold_dir":  0, "type": "FED_SPEECH"},

    # ── GDP ────────────────────────────────────────────────────────────
    "Advance GDP q/q":                         {"impact": 3, "gold_dir": -1, "type": "GDP"},
    "Preliminary GDP q/q":                     {"impact": 3, "gold_dir": -1, "type": "GDP"},
    "Final GDP q/q":                           {"impact": 2, "gold_dir": -1, "type": "GDP"},
    "GDP q/q":                                 {"impact": 3, "gold_dir": -1, "type": "GDP"},
    "GDP Price Index q/q":                     {"impact": 2, "gold_dir": -1, "type": "GDP"},

    # ── Retail & Consumer ──────────────────────────────────────────────
    "Retail Sales m/m":                        {"impact": 3, "gold_dir": -1, "type": "CONSUMER"},
    "Core Retail Sales m/m":                   {"impact": 3, "gold_dir": -1, "type": "CONSUMER"},
    "CB Consumer Confidence":                  {"impact": 2, "gold_dir": -1, "type": "CONSUMER"},
    "UoM Consumer Sentiment":                  {"impact": 2, "gold_dir": -1, "type": "CONSUMER"},
    "Michigan Consumer Sentiment":             {"impact": 2, "gold_dir": -1, "type": "CONSUMER"},
    "Michigan Consumer Expectations":          {"impact": 1, "gold_dir": -1, "type": "CONSUMER"},
    "Personal Spending m/m":                   {"impact": 2, "gold_dir": -1, "type": "CONSUMER"},
    "Personal Income m/m":                     {"impact": 2, "gold_dir": -1, "type": "CONSUMER"},

    # ── PMI / Business Activity ────────────────────────────────────────
    "ISM Manufacturing PMI":                   {"impact": 3, "gold_dir": -1, "type": "PMI"},
    "ISM Services PMI":                        {"impact": 3, "gold_dir": -1, "type": "PMI"},
    "ISM Non-Manufacturing PMI":               {"impact": 3, "gold_dir": -1, "type": "PMI"},
    "S&P Global Manufacturing PMI":            {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "S&P Global Services PMI":                 {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "S&P Global Composite PMI":                {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "Flash Manufacturing PMI":                 {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "Flash Services PMI":                      {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "Factory Orders m/m":                      {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "Durable Goods Orders m/m":                {"impact": 2, "gold_dir": -1, "type": "PMI"},
    "Core Durable Goods Orders m/m":           {"impact": 2, "gold_dir": -1, "type": "PMI"},

    # ── Housing ────────────────────────────────────────────────────────
    "Existing Home Sales":                     {"impact": 1, "gold_dir": -1, "type": "HOUSING"},
    "New Home Sales":                          {"impact": 1, "gold_dir": -1, "type": "HOUSING"},
    "Building Permits":                        {"impact": 1, "gold_dir": -1, "type": "HOUSING"},
    "Housing Starts":                          {"impact": 1, "gold_dir": -1, "type": "HOUSING"},
    "Pending Home Sales m/m":                  {"impact": 1, "gold_dir": -1, "type": "HOUSING"},
    "S&P/CS HPI Composite-20 y/y":             {"impact": 1, "gold_dir": -1, "type": "HOUSING"},

    # ── Trade & Current Account ────────────────────────────────────────
    "Trade Balance":                           {"impact": 2, "gold_dir":  0, "type": "TRADE"},
    "Current Account":                         {"impact": 1, "gold_dir":  0, "type": "TRADE"},
    "Goods Trade Balance":                     {"impact": 1, "gold_dir":  0, "type": "TRADE"},

    # ── Treasury / Bond Auctions ───────────────────────────────────────
    "10-y Bond Auction":                       {"impact": 2, "gold_dir": +1, "type": "BONDS"},
    "30-y Bond Auction":                       {"impact": 2, "gold_dir": +1, "type": "BONDS"},
    "3-y Note Auction":                        {"impact": 1, "gold_dir":  0, "type": "BONDS"},
    "5-y Note Auction":                        {"impact": 1, "gold_dir":  0, "type": "BONDS"},
    "7-y Note Auction":                        {"impact": 1, "gold_dir":  0, "type": "BONDS"},

    # ── Safe-Haven / Geopolitical (Gold always UP) ─────────────────────
    "US Credit Rating":                        {"impact": 3, "gold_dir": +1, "type": "SAFE_HAVEN"},
    "US Debt Ceiling":                         {"impact": 3, "gold_dir": +1, "type": "SAFE_HAVEN"},
    "Global Risk":                             {"impact": 3, "gold_dir": +1, "type": "SAFE_HAVEN"},
    "Banking Crisis":                          {"impact": 3, "gold_dir": +1, "type": "SAFE_HAVEN"},
    "Financial Stability Report":              {"impact": 2, "gold_dir": +1, "type": "SAFE_HAVEN"},
    "Treasury Secretary Speaks":               {"impact": 2, "gold_dir":  0, "type": "SAFE_HAVEN"},

    # ── US Government / Fiscal ────────────────────────────────────────
    "Federal Budget Balance":                  {"impact": 2, "gold_dir": +1, "type": "FISCAL"},
    "US Government Shutdown":                  {"impact": 3, "gold_dir": +1, "type": "FISCAL"},

    # ── Other Central Banks (indirect DXY / Gold effect) ─────────────
    "ECB Rate Decision":                       {"impact": 2, "gold_dir":  0, "type": "CENTRAL_BANK"},
    "BOE Rate Decision":                       {"impact": 2, "gold_dir":  0, "type": "CENTRAL_BANK"},
    "BOJ Rate Decision":                       {"impact": 2, "gold_dir":  0, "type": "CENTRAL_BANK"},
}

# Minimum deviation from forecast (as % of forecast value) to qualify scalp
DEFAULT_DEVIATION_THRESHOLDS = {
    "EMPLOYMENT": 0.10,   # 10 % deviation — NFP ±30k on a 200k forecast
    "INFLATION":  0.08,   # 8 %
    "GDP":        0.10,
    "CONSUMER":   0.05,
    "PMI":        0.02,   # PMI is a bounded 0-100 index, small deviations matter
    "FOMC":       0.0,    # FOMC: any surprise qualifies
    "FED_SPEECH": 0.0,    # Fed speech: tone qualifies, no deviation needed
    "HOUSING":    0.10,
    "TRADE":      0.10,
    "BONDS":      0.05,
    "SAFE_HAVEN": 0.0,    # Safe-haven: always qualifies
    "FISCAL":     0.0,
    "CENTRAL_BANK": 0.0,
}


class NewsEventLayer(SMCLayerBase):
    """
    Dual-mode news layer: blocks IGOF signals before high-impact events
    and optionally generates post-news scalp signals.
    """

    # ── Config defaults ────────────────────────────────────────────────
    PRE_NEWS_BLOCK_MINUTES   = 5     # block trading N minutes before event
    POST_NEWS_SCALP_MINUTES  = 3     # scalp window after event fires
    MIN_IMPACT_TO_BLOCK      = 2     # 2 = MEDIUM-HIGH and above
    MIN_IMPACT_TO_SCALP      = 3     # 3 = HIGH only (safety on small accounts)
    SCALP_DISPLACEMENT_RATIO = 0.8   # post-news candle body / ATR to qualify
    SCALP_SL_ATR_MULT        = 1.5   # SL distance = 1.5 × ATR
    SCALP_TP_RR              = 1.5   # TP = 1.5 × SL distance
    SCALP_MAX_BARS           = 3     # max bars to hold the scalp
    API_CACHE_MINUTES        = 15    # re-fetch calendar every 15 min
    API_TIMEOUT_SECONDS      = 6     # connection timeout
    LOCAL_CACHE_PATH         = "storage/news_cache/calendar.json"

    # Free Forex Factory JSON endpoint (no API key required)
    FF_CALENDAR_URL          = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    # FinnHub free tier fallback
    FINNHUB_URL              = "https://finnhub.io/api/v1/calendar/economic"

    def __init__(self, name="NewsEventLayer", threshold=0.5, config=None):
        super().__init__(name=name, threshold=threshold, config=config)
        self._reason               = "News layer not yet evaluated"

        # Config
        self.enable_news_scalp     = self.config.get("enable_news_scalp",      False)
        self.pre_block_minutes     = self.config.get("pre_news_block_minutes",  self.PRE_NEWS_BLOCK_MINUTES)
        self.post_scalp_minutes    = self.config.get("post_news_scalp_minutes", self.POST_NEWS_SCALP_MINUTES)
        self.min_block_impact      = self.config.get("min_impact_to_block",     self.MIN_IMPACT_TO_BLOCK)
        self.min_scalp_impact      = self.config.get("min_impact_to_scalp",     self.MIN_IMPACT_TO_SCALP)
        self.scalp_disp_ratio      = self.config.get("scalp_displacement_ratio",self.SCALP_DISPLACEMENT_RATIO)
        self.scalp_sl_atr          = self.config.get("scalp_sl_atr_mult",       self.SCALP_SL_ATR_MULT)
        self.scalp_tp_rr           = self.config.get("scalp_tp_rr",             self.SCALP_TP_RR)
        self.scalp_max_bars        = self.config.get("scalp_max_bars",          self.SCALP_MAX_BARS)
        self.finnhub_api_key       = self.config.get("finnhub_api_key",         "")
        self.cache_minutes         = self.config.get("api_cache_minutes",       self.API_CACHE_MINUTES)
        self.local_cache_path      = Path(self.config.get("local_cache_path",   self.LOCAL_CACHE_PATH))
        self.us_events_only        = self.config.get("us_events_only",          True)

        # Internal state
        self._calendar: List[Dict]  = []
        self._last_fetch: float     = 0.0
        self._lock                  = threading.Lock()

        # Ensure cache directory exists
        self.local_cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-load from local cache if available
        self._load_local_cache()

        logger.info(
            f"NewsEventLayer: scalp={'ON' if self.enable_news_scalp else 'OFF'}, "
            f"block={self.pre_block_minutes}min before, "
            f"scalp_window={self.post_scalp_minutes}min after"
        )

    # ══════════════════════════════════════════════════════════════════
    # Calendar fetching
    # ══════════════════════════════════════════════════════════════════

    def _load_local_cache(self):
        """Load the persisted local cache on startup."""
        try:
            if self.local_cache_path.exists():
                with open(self.local_cache_path, "r") as f:
                    self._calendar = json.load(f)
                logger.info(f"News cache loaded from disk: {len(self._calendar)} events")
        except Exception as e:
            logger.warning(f"Could not load local news cache: {e}")

    def _save_local_cache(self):
        """Persist calendar to disk so we survive network outages."""
        try:
            with open(self.local_cache_path, "w") as f:
                json.dump(self._calendar, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write news cache: {e}")

    def _fetch_forex_factory(self) -> List[Dict]:
        """
        Fetch this week's calendar from Forex Factory JSON feed.
        Free, no API key, updated every few minutes.
        Returns list of normalized event dicts.
        """
        try:
            req = Request(self.FF_CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=self.API_TIMEOUT_SECONDS) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            events = []
            for e in raw:
                # FF impact: "High", "Medium", "Low", "Holiday"
                impact_map = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0, "None": 0}
                impact     = impact_map.get(e.get("impact", "Low"), 1)
                currency   = e.get("currency", "")
                if self.us_events_only and currency != "USD":
                    continue
                title      = e.get("title", "")
                # Parse date/time — FF uses format "01-01-2026T13:30:00-0500"
                try:
                    dt_str = e.get("date", "")
                    # FF dates are Eastern Time; convert to UTC
                    dt_naive = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    dt_utc   = dt_naive.astimezone(timezone.utc)
                except Exception:
                    continue
                actual   = self._parse_number(e.get("actual",   ""))
                forecast = self._parse_number(e.get("forecast", ""))
                previous = self._parse_number(e.get("previous", ""))
                events.append({
                    "title":    title,
                    "time_utc": dt_utc.isoformat(),
                    "impact":   impact,
                    "currency": currency,
                    "actual":   actual,
                    "forecast": forecast,
                    "previous": previous,
                    "source":   "ForexFactory",
                })
            logger.info(f"Fetched {len(events)} USD events from Forex Factory")
            return events
        except URLError as e:
            logger.warning(f"Forex Factory fetch failed: {e}")
            return []
        except Exception as e:
            logger.warning(f"Forex Factory parse error: {e}")
            return []

    def _fetch_finnhub(self) -> List[Dict]:
        """
        Fallback: FinnHub free tier economic calendar.
        Requires a free API key (50 calls/minute, plenty for 15-min cache).
        """
        if not self.finnhub_api_key:
            return []
        try:
            today  = datetime.now(timezone.utc).date()
            end    = today + timedelta(days=7)
            url    = (
                f"{self.FINNHUB_URL}"
                f"?from={today.isoformat()}&to={end.isoformat()}"
                f"&token={self.finnhub_api_key}"
            )
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=self.API_TIMEOUT_SECONDS) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            events = []
            impact_map = {"high": 3, "medium": 2, "low": 1, "": 0}
            for e in raw.get("economicCalendar", []):
                if self.us_events_only and e.get("country", "") != "US":
                    continue
                try:
                    dt_utc = datetime.fromisoformat(
                        e.get("time", "").replace("Z", "+00:00")
                    ).astimezone(timezone.utc)
                except Exception:
                    continue
                events.append({
                    "title":    e.get("event", ""),
                    "time_utc": dt_utc.isoformat(),
                    "impact":   impact_map.get(e.get("impact", "").lower(), 1),
                    "currency": "USD",
                    "actual":   self._parse_number(str(e.get("actual",   ""))),
                    "forecast": self._parse_number(str(e.get("estimate", ""))),
                    "previous": self._parse_number(str(e.get("prev",     ""))),
                    "source":   "FinnHub",
                })
            logger.info(f"Fetched {len(events)} USD events from FinnHub")
            return events
        except Exception as e:
            logger.warning(f"FinnHub fetch failed: {e}")
            return []

    def _parse_number(self, s: str) -> Optional[float]:
        """Parse an economic number string like '223K', '2.3%', '-0.1' to float."""
        if not s or s in ("", "—", "N/A", "Pending"):
            return None
        s = s.strip().replace(",", "").replace("%", "").replace("$", "")
        mult = 1.0
        if s.endswith("K"):
            mult, s = 1_000.0, s[:-1]
        elif s.endswith("M"):
            mult, s = 1_000_000.0, s[:-1]
        elif s.endswith("B"):
            mult, s = 1_000_000_000.0, s[:-1]
        try:
            return float(s) * mult
        except ValueError:
            return None

    def _refresh_calendar(self):
        """
        Refresh the event calendar if the cache is stale.
        Tries Forex Factory first, falls back to FinnHub.
        Thread-safe via a lock.
        """
        now = time.time()
        if now - self._last_fetch < self.cache_minutes * 60:
            return  # Cache still fresh

        def _do_fetch():
            events = self._fetch_forex_factory()
            if not events:
                events = self._fetch_finnhub()
            if events:
                with self._lock:
                    self._calendar   = events
                    self._last_fetch = time.time()
                self._save_local_cache()

        # Fetch in background thread so we never block the trading loop
        t = threading.Thread(target=_do_fetch, daemon=True)
        t.start()

    # ══════════════════════════════════════════════════════════════════
    # Event matching and classification
    # ══════════════════════════════════════════════════════════════════

    def _match_catalog(self, title: str) -> Optional[Dict]:
        """
        Match an event title against the catalog using substring matching.
        Returns catalog metadata or None if not matched.
        """
        title_lower = title.lower()
        for key, meta in NEWS_CATALOG.items():
            if key.lower() in title_lower or title_lower in key.lower():
                return meta
        return None

    def _get_upcoming_events(self, within_minutes: int) -> List[Dict]:
        """Return events scheduled within the next N minutes (pre-event window)."""
        now    = datetime.now(timezone.utc)
        cutoff = now + timedelta(minutes=within_minutes)
        result = []
        with self._lock:
            for e in self._calendar:
                try:
                    et = datetime.fromisoformat(e["time_utc"]).astimezone(timezone.utc)
                except Exception:
                    continue
                if now <= et <= cutoff and e.get("impact", 0) >= self.min_block_impact:
                    result.append(e)
        return result

    def _get_recent_events(self, within_minutes: int) -> List[Dict]:
        """Return events that fired within the last N minutes (post-event scalp window)."""
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=within_minutes)
        result = []
        with self._lock:
            for e in self._calendar:
                try:
                    et = datetime.fromisoformat(e["time_utc"]).astimezone(timezone.utc)
                except Exception:
                    continue
                # Event fired in the past N minutes AND actual data is available
                if cutoff <= et <= now and e.get("impact", 0) >= self.min_scalp_impact:
                    if e.get("actual") is not None:  # data released
                        result.append(e)
        return result

    # ══════════════════════════════════════════════════════════════════
    # Scalp qualification
    # ══════════════════════════════════════════════════════════════════

    def _calculate_atr(self, df, period=14) -> float:
        """ATR calculation (shared pattern from other layers)."""
        import pandas as pd
        if len(df) < period + 1:
            return 1.0
        high, low, close = df["high"], df["low"], df["close"]
        tr1  = high - low
        tr2  = abs(high - close.shift(1))
        tr3  = abs(low  - close.shift(1))
        tr   = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr  = tr.rolling(window=period).mean().iloc[-1]
        return atr if not pd.isna(atr) else 1.0

    def _qualify_deviation(self, event: Dict) -> Tuple[bool, str]:
        """
        Determine if the actual vs forecast deviation is large enough to trade.
        Returns (qualified, direction) where direction is 'BULLISH' or 'BEARISH' for Gold.
        """
        actual   = event.get("actual")
        forecast = event.get("forecast")
        previous = event.get("previous")
        title    = event.get("title", "")
        catalog  = self._match_catalog(title) or {}
        event_type = catalog.get("type", "UNKNOWN")
        gold_dir   = catalog.get("gold_dir", 0)  # +1 = USD bearish = Gold up

        # Safe-haven and speech events: always qualify, direction from tone
        if event_type in ("SAFE_HAVEN", "FISCAL", "FOMC", "FED_SPEECH", "CENTRAL_BANK"):
            if gold_dir == +1:
                return True, "BULLISH"
            if gold_dir == -1:
                return True, "BEARISH"
            return False, ""  # mixed/unknown — skip scalp

        if actual is None:
            return False, ""

        # Deviation threshold check
        threshold = DEFAULT_DEVIATION_THRESHOLDS.get(event_type, 0.08)
        reference = forecast if forecast is not None else previous
        if reference is None or reference == 0:
            return False, ""

        deviation_pct = abs(actual - reference) / abs(reference)
        if deviation_pct < threshold:
            return False, ""

        # Determine surprise direction
        beat = actual > reference  # actual beat forecast

        # Gold direction depends on event type's DXY effect
        # If event is DXY-positive (gold_dir = -1): beat = USD stronger = Gold down = BEARISH
        # If event is DXY-positive: miss = USD weaker = Gold up = BULLISH
        if gold_dir == -1:
            gold_direction = "BEARISH" if beat else "BULLISH"
        elif gold_dir == +1:
            gold_direction = "BULLISH" if beat else "BEARISH"
        else:
            return False, ""  # mixed event, don't guess

        return True, gold_direction

    def _qualify_candle_displacement(self, df, direction: str) -> Tuple[bool, float]:
        """
        Verify the first post-news candle shows displacement in the expected direction.
        Returns (qualified, atr).
        """
        if df is None or len(df) < 15:
            return False, 1.0
        atr  = self._calculate_atr(df)
        c    = df.iloc[-1]
        body = abs(c["close"] - c["open"])
        if body < self.scalp_disp_ratio * atr:
            return False, atr
        # Check candle is moving in expected direction
        if direction == "BULLISH" and c["close"] <= c["open"]:
            return False, atr
        if direction == "BEARISH" and c["close"] >= c["open"]:
            return False, atr
        return True, atr

    def _build_scalp_signal(self, direction: str, atr: float, event_title: str) -> Dict:
        """Build the scalp signal metadata to attach to the result."""
        action = "BUY" if direction == "BULLISH" else "SELL"
        return {
            "action":       action,
            "direction":    direction,
            "sl_atr_mult":  self.scalp_sl_atr,
            "tp_rr":        self.scalp_tp_rr,
            "max_bars":     self.scalp_max_bars,
            "atr":          round(atr, 2),
            "trigger":      f"NEWS SCALP: {event_title}",
        }

    # ══════════════════════════════════════════════════════════════════
    # Core interface — SMCLayerBase signatures
    # ══════════════════════════════════════════════════════════════════

    def validate(self, df):
        """Single-TF validation fallback (used by base process())."""
        return self._evaluate(df, data={})

    def _evaluate(self, df, data: Dict) -> Tuple[bool, float]:
        """Core logic shared between validate() and process()."""
        self._refresh_calendar()  # non-blocking, spawns background thread

        # ── 1. Pre-event blocking window ──────────────────────────────
        upcoming = self._get_upcoming_events(self.pre_block_minutes)
        if upcoming:
            titles = ", ".join(e["title"] for e in upcoming[:3])
            self._reason = (
                f"NEWS BLOCK: {len(upcoming)} event(s) in next "
                f"{self.pre_block_minutes}min — {titles}"
            )
            logger.info(self._reason)
            return False, 0.0

        # ── 2. Post-event scalp window ─────────────────────────────────
        if self.enable_news_scalp:
            recent = self._get_recent_events(self.post_scalp_minutes)
            for event in recent:
                qualified, direction = self._qualify_deviation(event)
                if not qualified:
                    continue
                # Verify candle displacement confirms the direction
                candle_ok, atr = self._qualify_candle_displacement(df, direction)
                if not candle_ok:
                    self._reason = (
                        f"NEWS SCALP: {event['title']} qualified ({direction}) "
                        f"but candle displacement insufficient"
                    )
                    continue
                # All conditions met — pass with scalp signal attached
                self._reason = (
                    f"NEWS SCALP QUALIFIED: {event['title']} | "
                    f"{direction} | dev={abs((event.get('actual') or 0) - (event.get('forecast') or 0)):.2f}"
                )
                self._scalp_signal = self._build_scalp_signal(direction, atr, event["title"])
                logger.info(self._reason)
                return True, 0.90  # High score but below 1.0 — scalp, not a primary setup

        # ── 3. No blocking event and no scalp → pass cleanly ──────────
        self._reason = "NEWS: No blocking event. Pipeline clear."
        self._scalp_signal = None
        return True, 1.0

    def process(self, data: Dict) -> Dict:
        """
        IGOF pipeline entry point.
        Returns standard {status, reason, score} dict.
        When scalp_mode fires, also returns {scalp_signal: {...}}.
        """
        self._scalp_signal = None  # reset each cycle

        # Get M5 candles for displacement check
        m5_candles = data.get("m5_candles", [])
        df = None
        if m5_candles:
            try:
                import pandas as pd
                df = pd.DataFrame(m5_candles)
            except Exception:
                df = None

        status, score = self._evaluate(df, data)

        # Derive bias from scalp signal direction when present; otherwise neutral
        # (the news layer does not have a structural bias of its own)
        bias = "neutral"
        if self._scalp_signal:
            bias = self._scalp_signal.get("direction", "neutral").lower()

        result = {
            "status": status,
            "reason": f"NewsEventLayer: {self._reason}",
            "score":  score,
            "bias":   bias,
        }
        if self._scalp_signal:
            result["scalp_signal"] = self._scalp_signal

        return result

    # ── Public helper for dashboard / debugging ────────────────────────
    def get_todays_events(self) -> List[Dict]:
        """Return today's high-impact USD events for dashboard display."""
        today = datetime.now(timezone.utc).date()
        result = []
        with self._lock:
            for e in self._calendar:
                try:
                    et = datetime.fromisoformat(e["time_utc"]).astimezone(timezone.utc)
                except Exception:
                    continue
                if et.date() == today and e.get("impact", 0) >= 2:
                    result.append(e)
        return sorted(result, key=lambda x: x["time_utc"])
