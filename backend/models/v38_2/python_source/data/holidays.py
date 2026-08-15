"""Deterministic XAUUSD spot-market holiday calendar.

The XAUUSD spot market (OTC gold, as served by Dukascopy and most FX brokers)
closes on a small, well-defined set of public holidays. This module provides a
DETERMINISTIC calendar of those holiday dates so gap analysis can distinguish a
legitimate MARKET_CLOSED_HOLIDAY gap (the exchange was genuinely closed) from an
UNEXPECTED_GAP (possible missing data).

No bars are fabricated. No gap is classified as a holiday by duration alone — a
gap is only MARKET_CLOSED_HOLIDAY when the gap's date range contains one of the
authoritative holiday dates below.

Holidays recognised for the XAUUSD spot market:
  - New Year's Day           Jan 1
  - Good Friday              (Easter Sunday − 2 days, via the computus)
  - Easter Monday            (Easter Sunday + 1 day)
  - Christmas Day            Dec 25
  - Boxing Day               Dec 26

Easter dates are computed with the Meeus/Jones/Butcher algorithm (the Gregorian
computus), which is the authoritative method used by western Christian calendars.
It is deterministic and reproducible for any year.
"""
from __future__ import annotations

from datetime import date, timedelta


def easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday via the Meeus/Jones/Butcher computus.

    Deterministic, reproducible, valid for any Gregorian year.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# Fixed-date holidays (month, day).
_FIXED_HOLIDAYS = [
    (1, 1),     # New Year's Day
    (12, 25),   # Christmas Day
    (12, 26),   # Boxing Day
]


def xauusd_market_holidays(year: int) -> set[date]:
    """Return the set of XAUUSD spot-market holiday dates for a given year."""
    holidays: set[date] = set()
    for month, day in _FIXED_HOLIDAYS:
        holidays.add(date(year, month, day))
    easter = easter_sunday(year)
    holidays.add(easter - timedelta(days=2))   # Good Friday
    holidays.add(easter + timedelta(days=1))   # Easter Monday
    return holidays


def holidays_for_range(start: date, end: date) -> set[date]:
    """Return all XAUUSD holiday dates in [start, end] (inclusive)."""
    out: set[date] = set()
    for year in range(start.year, end.year + 1):
        ys = xauusd_market_holidays(year)
        out |= {d for d in ys if start <= d <= end}
    return out


def gap_contains_holiday(start_ts, end_ts) -> bool:
    """True iff a known XAUUSD holiday falls within [start_ts, end_ts] dates.

    start_ts / end_ts are pandas Timestamps (any tz). The check is on calendar
    dates only, so a holiday that falls on a weekend day (observed closure may
    shift) still matches when it lies inside the gap's date range.
    """
    d_start = pd_date(start_ts)
    d_end = pd_date(end_ts)
    return any(
        d in xauusd_market_holidays(d.year)
        for d in _date_range(d_start, d_end)
    )


def pd_date(ts) -> date:
    """Extract a calendar date from a pandas Timestamp or datetime."""
    if ts is None:
        return date(1970, 1, 1)
    try:
        return ts.date()
    except AttributeError:
        return ts


def _date_range(d_start: date, d_end: date) -> list[date]:
    """Inclusive list of dates from d_start to d_end."""
    out = []
    cur = d_start
    while cur <= d_end:
        out.append(cur)
        cur += timedelta(days=1)
    return out
