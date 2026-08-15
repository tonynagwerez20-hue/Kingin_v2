"""Gap analysis — distinguishes expected weekend/market-closure gaps from
unexpected intraday gaps. No bars are ever fabricated to fill gaps.

Gap classes:
  WEEKEND_GAP            — normal Friday→Sunday/Monday closure spanning a
                           Saturday/Sunday but NOT containing a holiday.
  MARKET_CLOSED_HOLIDAY  — a gap whose date range contains a known XAUUSD
                           spot-market holiday (Christmas, New Year, Good
                           Friday, Easter Monday, Boxing Day). Classified via
                           the deterministic holiday calendar in holidays.py —
                           NEVER by duration alone.
  DAILY_ROLLOVER_GAP     — a weekday gap <= the modal recurring daily break.
  UNEXPECTED_GAP         — any remaining gap; potential data issue.

The raw max gap duration is preserved in ``max_gap_hours`` (unchanged). A new
``max_unexpected_gap_hours`` reports the largest gap among UNEXPECTED gaps only,
so the readiness threshold can be applied to missing-data gaps rather than to
expected market closures.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .schema import TF_RULES
from .holidays import gap_contains_holiday


def analyze_gaps(df: pd.DataFrame, tf: str) -> dict:
    """Classify inter-bar gaps into market-closure (expected) vs unexpected.

    FX/gold trades ~5.5 days/week with a daily market closure (rollover) and a
    weekend closure. Both are EXPECTED. Holiday closures (Christmas, Easter,
    New Year) are EXPECTED and classified via the deterministic holiday calendar.

      WEEKEND_GAP           — gap spans a Saturday/Sunday and contains NO holiday.
      MARKET_CLOSED_HOLIDAY — gap date range contains a known XAUUSD holiday.
      DAILY_ROLLOVER_GAP    — a weekday gap <= the recurring daily closure.
      UNEXPECTED_GAP        — any remaining gap larger than expected; reported.

    These counts are diagnostic only. No bars are ever fabricated to fill gaps.
    """
    if len(df) < 2:
        return {"weekend_gap_count": 0, "market_closed_holiday_count": 0,
                "daily_rollover_gap_count": 0, "unexpected_gap_count": 0,
                "unexpected_gap_examples": [],
                "market_closed_holiday_examples": [],
                "max_gap_hours": 0.0, "max_unexpected_gap_hours": 0.0}
    ts = pd.DatetimeIndex(df["ts"])
    starts = ts[:-1]
    ends = ts[1:]
    deltas = (ends - starts)
    expected = pd.Timedelta(TF_RULES.get(tf, "1h"))

    # modal recurring daily-closure gap: among weekday gaps > expected*1.5 that
    # do NOT span a weekend, take the most common gap rounded to the hour. Daily
    # market closures are short; cap the rollover threshold so a genuinely large
    # weekday gap is still flagged as unexpected. A weekday gap > 3h that is not
    # the recurring daily-closure pattern is unexpected.
    weekday_gaps = []
    for i in range(len(deltas)):
        d = deltas[i]
        if d <= expected * 1.5:
            continue
        s = starts[i]
        span = pd.date_range(s, ends[i], freq="1h").weekday
        if not ((span == 5).any() or (span == 6).any()):
            weekday_gaps.append((s, ends[i], d))
    from collections import Counter
    if weekday_gaps:
        modal_h = Counter(int(round(g.total_seconds() / 3600)) for _, _, g in weekday_gaps).most_common(1)[0][0]
    else:
        modal_h = 0
    # rollover = the recurring daily closure only (small); cap at 3h so large
    # weekday gaps are flagged, unless the modal daily closure is itself larger
    # (e.g. a broker with a longer daily break) — in which case allow up to that.
    rollover_threshold = pd.Timedelta(hours=max(min(modal_h, 3), 2))

    weekend = 0; holiday = 0; rollover = 0; unexpected = []
    holiday_examples = []
    max_unexpected = 0.0
    for i in range(len(deltas)):
        d = deltas[i]
        if d <= expected * 1.5:
            continue
        s = starts[i]
        span = pd.date_range(s, ends[i], freq="1h").weekday
        spans_weekend = (span == 5).any() or (span == 6).any()
        contains_holiday = gap_contains_holiday(s, ends[i])
        if contains_holiday:
            # A gap whose date range contains a known market holiday is a
            # legitimate market closure — regardless of duration or weekend
            # overlap. Classified by the deterministic calendar, not duration.
            holiday += 1
            holiday_examples.append({"after": str(s), "before": str(ends[i]),
                                     "gap_hours": round(d.total_seconds() / 3600.0, 2)})
        elif spans_weekend:
            weekend += 1
        elif d <= rollover_threshold:
            rollover += 1
        else:
            unexpected.append({"after": str(s), "before": str(ends[i]),
                                "gap_hours": round(d.total_seconds() / 3600.0, 2)})
            gap_h = d.total_seconds() / 3600.0
            if gap_h > max_unexpected:
                max_unexpected = gap_h
    return {
        "weekend_gap_count": int(weekend),
        "market_closed_holiday_count": int(holiday),
        "daily_rollover_gap_count": int(rollover),
        "unexpected_gap_count": len(unexpected),
        "unexpected_gap_examples": unexpected[:10],
        "market_closed_holiday_examples": holiday_examples[:15],
        "max_gap_hours": round(float(deltas.max().total_seconds()) / 3600.0, 2) if len(deltas) else 0.0,
        "max_unexpected_gap_hours": round(max_unexpected, 2),
    }
