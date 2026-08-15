"""Forex Factory historical calendar acquisition.

Fetches USD Tier-1 events from Forex Factory's historical calendar pages,
week by week, from 2018-01-01 to the latest available date.

Extracts: event timestamp (ET→UTC), currency, impact, event name, actual,
forecast, previous. No fabrication — only values shown by FF are recorded.

FF URL pattern: https://www.forexfactory.com/calendar?week=MMMDD.YYYY
  e.g. week=jan1.2018 returns the week containing Jan 1, 2018.

FF times are in US/Eastern time (ET). They are converted to UTC on ingest.
FF does NOT expose a release-timestamp/LastUpdate field — the event time IS
the release time. Historical forecasts are preserved by FF but without a
pre-release timestamp proof, so they are labeled PIT_UNVERIFIED downstream.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .tier1_mapping import match_tier1, TIER1_EVENTS

FF_BASE = "https://www.forexfactory.com/calendar"
FF_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# ET timezone (US/Eastern) — FF uses ET. We handle EST/EDT via the zoneinfo
# library which is available in Python 3.9+.
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except ImportError:
    ET = timezone(timedelta(hours=-5))  # fallback: EST

RAW_CACHE_DIR = Path(__file__).resolve().parents[4] / "data" / "ff_raw"


def _week_url(week_start: datetime) -> str:
    """Build FF URL for the week containing week_start."""
    day_str = week_start.strftime("%b%d.%Y").lstrip("0")
    # FF uses lowercase month + no leading zero on day: jan1.2018
    day_str = week_start.strftime("%b%e.%Y").replace(" ", "").lower()
    return f"{FF_BASE}?week={day_str}"


def _fetch_week(week_start: datetime, cache: bool = True) -> str | None:
    """Fetch one week of FF calendar HTML. Returns HTML string or None."""
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = RAW_CACHE_DIR / f"week_{week_start.strftime('%Y%m%d')}.html"
    if cache and cache_file.exists():
        return cache_file.read_text(encoding="windows-1252", errors="replace")

    url = _week_url(week_start)
    req = urllib.request.Request(url, headers={"User-Agent": FF_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("windows-1252", errors="replace")
    except Exception as e:
        return None
    if cache:
        cache_file.write_text(html, encoding="utf-8")
    time.sleep(1.0)  # respectful delay
    return html


def _parse_ff_value(s: str) -> str:
    """Clean an FF cell value: strip HTML, whitespace, and FF formatting."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    # FF uses special characters: &nbsp; → space, &amp; → &
    s = s.replace("\xa0", " ").replace("&amp;", "&").replace("&nbsp;", " ")
    return s.strip()


def _parse_impact(row_html: str) -> str:
    """Extract impact level from FF row HTML.

    FF uses icon classes: icon--ff-impact-red (high), icon--ff-impact-orange
    (medium), icon--ff-impact-yellow (low). Also checks impact--high etc.
    """
    if "icon--ff-impact-red" in row_html or "impact--high" in row_html:
        return "high"
    if "icon--ff-impact-ora" in row_html or "impact--medium" in row_html or "impact--med" in row_html:
        return "medium"
    if "icon--ff-impact-yel" in row_html or "impact--low" in row_html:
        return "low"
    if "impact--holiday" in row_html:
        return "holiday"
    return "none"


def _parse_time_to_utc(time_str: str, date_str: str) -> Optional[datetime]:
    """Convert FF time (ET) + date to UTC datetime.

    time_str: '8:30am', '2:00pm', 'All Day', 'Tentative', ''
    date_str: 'Jan 1', 'Jan 2', etc. (from the date header for that row's week)
    """
    if not time_str or time_str in ("All Day", "Tentative", ""):
        return None
    # Parse time: '8:30am' or '2:00pm'
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    # Parse date: 'Jan 1' → need year from context
    # date_str format: 'Jan 1' or 'Jan  1'
    dm = re.match(r"(\w{3})\s+(\d{1,2})", date_str.strip())
    if not dm:
        return None
    month_str = dm.group(1)
    day = int(dm.group(2))

    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                 "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    month = month_map.get(month_str)
    if not month:
        return None

    # Year is determined by the week being fetched
    # (passed via the date context — we need the year)
    # This is handled by the caller who knows which week this is
    return None  # placeholder — year handled in _parse_week


def _parse_week(html: str, week_start: datetime) -> list[dict]:
    """Parse one week of FF calendar HTML into event records."""
    records = []
    if not html:
        return records

    year = week_start.year

    # Extract all <tr> tags (full, including attributes)
    all_trs = re.findall(r'(<tr[^>]*>.*?</tr>)', html, re.DOTALL)
    current_date_str = ""
    current_time = ""

    for tr in all_trs:
        # Check if this row starts a new date group
        date_match = re.search(
            r'>(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{1,2})<',
            tr)
        if date_match and 'calendar__date' in tr:
            current_date_str = f"{date_match.group(1)} {date_match.group(2)}"
            current_time = ""  # reset time for new date

        # Track time across ALL rows (time may appear on a non-USD row
        # that precedes grouped USD events sharing the same release time)
        cells_all = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if cells_all:
            t = _parse_ff_value(cells_all[0])
            if t:
                current_time = t

        # Only process USD event rows
        if 'USD' not in tr:
            continue
        if 'data-event-id' not in tr:
            continue

        cells = cells_all
        if len(cells) < 9:
            continue

        time_str = _parse_ff_value(cells[0])
        currency = _parse_ff_value(cells[1])
        if currency != "USD":
            continue

        # Use inherited time if this row's time is empty
        effective_time = time_str if time_str else current_time

        impact = _parse_impact(tr)
        event_name = _parse_ff_value(cells[3]) if len(cells) > 3 else ""
        actual = _parse_ff_value(cells[6]) if len(cells) > 6 else ""
        forecast = _parse_ff_value(cells[7]) if len(cells) > 7 else ""
        previous = _parse_ff_value(cells[8]) if len(cells) > 8 else ""

        if not event_name:
            continue

        # Match to Tier-1
        tier1 = match_tier1(event_name)
        if tier1 is None:
            continue

        # Parse timestamp: convert ET time + date to UTC
        ts_utc = _build_timestamp(effective_time, current_date_str, week_start)
        if ts_utc is None:
            continue

        record = {
            "ts": ts_utc,
            "country": "United States",
            "currency": "USD",
            "event_name_raw": event_name,
            "event_name": tier1["name"],
            "category": tier1["category"],
            "importance": 3 if impact == "high" else (2 if impact == "medium" else 1),
            "actual": _parse_numeric(actual),
            "forecast": _parse_numeric(forecast),
            "previous": _parse_numeric(previous),
            "actual_raw": actual,
            "forecast_raw": forecast,
            "previous_raw": previous,
            "unit": tier1["fred_units"],
            "directionality": tier1["directionality"],
            "fred_series": tier1["fred_series"],
            "fred_name": tier1["fred_name"],
            "is_pct": tier1["is_pct"],
            "pct_period": tier1["pct_period"],
            "freq": tier1["freq"],
            "impact_label": impact,
            "source": "forexfactory",
            "ff_time_et": effective_time,
            "ff_date": current_date_str,
            "ff_url": _week_url(week_start),
        }
        records.append(record)

    return records


def _build_timestamp(time_str: str, date_str: str, week_start: datetime) -> Optional[datetime]:
    """Build a UTC timestamp from FF time (ET) and date string."""
    if not time_str or time_str in ("All Day", "Tentative", ""):
        return None
    if not date_str:
        return None

    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    dm = re.match(r"(\w{3})\s+(\d{1,2})", date_str.strip())
    if not dm:
        return None
    month_str = dm.group(1)
    day = int(dm.group(2))

    month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                 "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    month = month_map.get(month_str)
    if not month:
        return None

    # Determine year: the week_start gives us the year context.
    # If the month is Jan but week_start is in Dec, the event is in the next year.
    # If the month is Dec but week_start is in Jan, the event is in the previous year.
    year = week_start.year
    if month == 1 and week_start.month == 12:
        year = week_start.year + 1
    elif month == 12 and week_start.month == 1:
        year = week_start.year - 1

    try:
        et_dt = datetime(year, month, day, hour, minute, tzinfo=ET)
    except ValueError:
        return None
    return et_dt.astimezone(timezone.utc)


def _parse_numeric(s: str) -> float | None:
    """Parse an FF numeric value. Returns None if not a number."""
    if not s:
        return None
    s = s.strip()
    # FF uses: '0.2%', '147K', '2.5B', '-0.1%', '47.2'
    s_clean = s.replace("%", "").replace("K", "").replace("B", "").replace("M", "").strip()
    if s_clean in ("", "—", "-", "..."):
        return None
    try:
        val = float(s_clean)
        if "K" in s:
            val *= 1000
        elif "M" in s:
            val *= 1_000_000
        elif "B" in s:
            val *= 1_000_000_000
        return val
    except (ValueError, TypeError):
        return None


def acquire_ff_range(start: datetime, end: datetime,
                     cache: bool = True, max_weeks: int | None = None) -> pd.DataFrame:
    """Acquire USD Tier-1 events from FF for the date range [start, end].

    Iterates week by week, fetches each FF calendar page, parses USD Tier-1
    events. Returns a DataFrame.
    """
    # Align start to the Monday of its week
    start_monday = start - timedelta(days=start.weekday())
    end_monday = end - timedelta(days=end.weekday())

    all_records = []
    current = start_monday
    weeks_done = 0
    total_weeks = (end_monday - start_monday).days // 7 + 1

    while current <= end_monday:
        if max_weeks and weeks_done >= max_weeks:
            break
        html = _fetch_week(current, cache=cache)
        if html:
            records = _parse_week(html, current)
            all_records.extend(records)
            weeks_done += 1
            if weeks_done % 10 == 0:
                print(f"  [ff] week {weeks_done}/{total_weeks}: "
                      f"{current.strftime('%Y-%m-%d')} — {len(records)} tier-1 events", flush=True)
        else:
            print(f"  [ff] FAILED week {current.strftime('%Y-%m-%d')}", flush=True)
        current += timedelta(days=7)

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def ff_obs_date_from_ts(ts: datetime, freq: str = "monthly") -> str:
    """For a given event timestamp, determine the FRED observation date.

    Monthly: observation is the prior month (e.g., CPI released Feb -> Jan obs).
    Quarterly: observation is the quarter being reported (e.g., GDP released
    Jan -> Q4 of previous year -> obs_date = Oct 1).
    """
    if ts is None:
        return ""
    if freq == "quarterly":
        release_month = ts.month
        if release_month in (1, 2, 3):
            return f"{ts.year - 1}-10-01"
        elif release_month in (4, 5, 6):
            return f"{ts.year}-01-01"
        elif release_month in (7, 8, 9):
            return f"{ts.year}-04-01"
        else:
            return f"{ts.year}-07-01"
    obs_month = ts.month - 1
    obs_year = ts.year
    if obs_month == 0:
        obs_month = 12
        obs_year -= 1
    return f"{obs_year}-{obs_month:02d}-01"


def ff_prev_obs_date_from_ts(ts: datetime, freq: str = "monthly") -> str:
    """The FRED observation date for the PREVIOUS period (for 'previous' value validation).

    Monthly: two months before release (the month before the current obs).
    Quarterly: the quarter before the one being reported.
    """
    if ts is None:
        return ""
    if freq == "quarterly":
        release_month = ts.month
        if release_month in (1, 2, 3):
            return f"{ts.year - 1}-07-01"
        elif release_month in (4, 5, 6):
            return f"{ts.year - 1}-10-01"
        elif release_month in (7, 8, 9):
            return f"{ts.year}-01-01"
        else:
            return f"{ts.year}-04-01"
    obs_month = ts.month - 2
    obs_year = ts.year
    if obs_month <= 0:
        obs_month += 12
        obs_year -= 1
    return f"{obs_year}-{obs_month:02d}-01"
