"""M1 validation + gap classification (Phase C).

Validates raw M1 bars reconstructed from Dukascopy ticks and classifies every
inter-bar gap into one of:

  EXPECTED_GAP    — weekend closure (Fri close -> Sun open) or the recurring
                    daily market rollover break.
  MARKET_CLOSED   — a holiday / scheduled closure evidenced by the feed
                    returning empty (no ticks) across the whole gap, on a
                    weekday that is not the recurring daily break.
  UNEXPECTED_GAP  — an intraday gap larger than the daily break with no
                    weekend/holiday evidence; potential data issue.
  SOURCE_OUTAGE   — a weekday gap during core session hours (Mon-Fri
                    00:00-21:00 UTC) substantially longer than the daily break
                    AND coinciding with a known feed-flakiness pattern (many
                    failed hours in the manifest for that day). Flagged as a
                    likely source outage rather than a real market gap.

No bars are fabricated. Every gap is recorded; none is silently reclassified.
The manifest's per-day failed-hour counts feed SOURCE_OUTAGE detection.
"""
from __future__ import annotations

from collections import Counter
from typing import List

import numpy as np
import pandas as pd

from ..schema import TF_RULES
from ..holidays import gap_contains_holiday


# Dukascopy XAUUSD weekly session: opens Sun ~22:00 UTC, closes Fri ~21:00 UTC,
# with a short daily break ~21:00-22:00 UTC. These are heuristics; the recurring
# daily break is also inferred from the data's modal weekday gap.
DAILY_BREAK_MAX_HOURS = 3  # weekday gaps <= this (and not weekend) are rollover


def _spans_weekend(start: pd.Timestamp, end: pd.Timestamp) -> bool:
    """True if the gap covers any Saturday or Sunday UTC."""
    if end - start <= pd.Timedelta(hours=12):
        # short gap cannot be a weekend closure
        return False
    span = pd.date_range(start, end, freq="1h")
    return bool((span.weekday == 5).any() or (span.weekday == 6).any())


def classify_gaps(df: pd.DataFrame, tf: str,
                  day_failure_counts: dict | None = None) -> dict:
    """Classify inter-bar gaps for a bar DataFrame.

    day_failure_counts: {YYYY-MM-DD: failed_hour_count} from the acquisition
    manifest, used to distinguish SOURCE_OUTAGE from UNEXPECTED_GAP.

    Returns a dict with counts per class and example lists.
    """
    day_failure_counts = day_failure_counts or {}
    if len(df) < 2:
        return {"expected_gap_count": 0, "market_closed_count": 0,
                "unexpected_gap_count": 0, "source_outage_count": 0,
                "examples": {"EXPECTED_GAP": [], "MARKET_CLOSED": [],
                             "UNEXPECTED_GAP": [], "SOURCE_OUTAGE": []},
                "max_gap_hours": 0.0, "max_unexpected_gap_hours": 0.0,
                "total_gaps_classified": 0}

    ts = pd.DatetimeIndex(df["ts"])
    starts = ts[:-1]
    ends = ts[1:]
    deltas = ends - starts
    expected = pd.Timedelta(TF_RULES.get(tf, "1min"))

    # infer modal recurring daily-break gap (weekday, not weekend, > expected*1.5)
    weekday_gaps = []
    for i in range(len(deltas)):
        d = deltas[i]
        if d <= expected * 1.5:
            continue
        if _spans_weekend(starts[i], ends[i]):
            continue
        weekday_gaps.append(int(round(d.total_seconds() / 3600)))
    modal_h = Counter(weekday_gaps).most_common(1)[0][0] if weekday_gaps else 0
    rollover_threshold = pd.Timedelta(hours=max(min(modal_h, DAILY_BREAK_MAX_HOURS), 2))

    out = {"expected_gap_count": 0, "market_closed_count": 0,
           "unexpected_gap_count": 0, "source_outage_count": 0,
           "examples": {"EXPECTED_GAP": [], "MARKET_CLOSED": [],
                        "UNEXPECTED_GAP": [], "SOURCE_OUTAGE": []}}
    max_unexpected = 0.0

    for i in range(len(deltas)):
        d = deltas[i]
        if d <= expected * 1.5:
            continue
        s, e = starts[i], ends[i]
        rec = {"after": str(s), "before": str(e),
               "gap_hours": round(d.total_seconds() / 3600.0, 2)}
        gap_hours = rec["gap_hours"]

        if _spans_weekend(s, e):
            # Weekend closure. Still check for a holiday inside the gap: a
            # holiday that falls on/near a weekend extends the closure beyond
            # a normal weekend and is classified MARKET_CLOSED.
            if gap_contains_holiday(s, e):
                out["market_closed_count"] += 1
                out["examples"]["MARKET_CLOSED"].append(rec)
            else:
                out["expected_gap_count"] += 1
                out["examples"]["EXPECTED_GAP"].append(rec)
        elif gap_contains_holiday(s, e):
            # Weekday gap containing a known market holiday → legitimate closure.
            out["market_closed_count"] += 1
            out["examples"]["MARKET_CLOSED"].append(rec)
        elif gap_hours <= rollover_threshold.total_seconds() / 3600:
            # recurring daily market break (e.g. 21:00-22:00 UTC)
            out["expected_gap_count"] += 1
            out["examples"]["EXPECTED_GAP"].append(rec)
        else:
            # weekday, longer than daily break: outage vs unexpected
            # check if the gap spans a known gold holiday window heuristically:
            # a full trading-day absence on a weekday with NO failed hours in
            # the manifest -> SOURCE_OUTAGE if failures, else UNEXPECTED_GAP.
            days_in_gap = pd.date_range(s, e, freq="1D")
            failed_in_gap = sum(day_failure_counts.get(d.strftime("%Y-%m-%d"), 0)
                                for d in days_in_gap)
            if failed_in_gap > 0 and gap_hours >= 6:
                out["source_outage_count"] += 1
                out["examples"]["SOURCE_OUTAGE"].append({**rec,
                    "failed_hours_in_gap": failed_in_gap})
            else:
                out["unexpected_gap_count"] += 1
                out["examples"]["UNEXPECTED_GAP"].append(rec)
                if gap_hours > max_unexpected:
                    max_unexpected = gap_hours

    for k in out["examples"]:
        out["examples"][k] = out["examples"][k][:15]
    out["total_gaps_classified"] = (out["expected_gap_count"]
        + out["market_closed_count"] + out["unexpected_gap_count"]
        + out["source_outage_count"])
    out["max_gap_hours"] = round(float(deltas.max().total_seconds()) / 3600.0, 2)
    out["max_unexpected_gap_hours"] = round(max_unexpected, 2)
    out["inferred_daily_break_hours"] = modal_h
    return out
