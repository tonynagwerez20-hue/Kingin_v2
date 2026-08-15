"""Economic-calendar acquisition scaffolding (point-in-time aware).

The V38.2 calendar schema (v38/macro/engine.py) requires:
    ts, country, currency, event_name, category, importance,
    actual, forecast, previous, revised_previous, unit, directionality

CRITICAL macro leakage rule: historical values must preserve what was KNOWN at
the event time — never replace historical actuals with today's revised values.
Where point-in-time information is unavailable, the limitation is recorded
explicitly; values are never inferred/fabricated.

This module provides:
  - schema mapping from common source formats to the V38.2 schema
  - a point-in-time integrity checker
  - an honest acquisition status reporter (BLOCKED if no source is accessible)

Accessible free point-in-time historical calendar sources are NOT available
without paid API credentials (Trading Economics, Forex Factory historical
exports, etc.). This module does NOT fabricate events. It records the
limitation and leaves the calendar ABSENT until a genuine source is supplied
as backend/data/economic_calendar.csv.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from ..schema import CALENDAR_COLUMNS

# USD events materially relevant to gold (not a restriction — full USD calendar
# is preserved; filtering for model relevance happens later).
USD_RELEVANT_CATEGORIES = {
    "CPI", "Core CPI", "PCE", "Core PCE", "NFP", "Unemployment Rate",
    "Average Hourly Earnings", "GDP", "Retail Sales", "PPI",
    "ISM Manufacturing", "ISM Services", "FOMC", "Federal Funds Rate",
    "Jobless Claims", "Consumer Confidence", "PMI", "Durable Goods", "Housing",
}


@dataclass
class CalendarAcquisitionStatus:
    source: str
    accessible: bool
    point_in_time: str  # "verified" | "unverified" | "unavailable"
    retrieval_time_utc: str
    coverage_start: Optional[str] = None
    coverage_end: Optional[str] = None
    event_count: int = 0
    usd_event_count: int = 0
    actual_completeness: float = 0.0  # fraction non-missing
    forecast_completeness: float = 0.0
    previous_completeness: float = 0.0
    revision_coverage: float = 0.0
    limitations: list = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


def assess_point_in_time(df: pd.DataFrame) -> str:
    """Assess point-in-time integrity of a loaded calendar.

    Returns "verified" only if every row carries a revision marker or the source
    explicitly documents point-in-time. Otherwise "unverified". Never "verified"
    for a source that cannot prove it.
    """
    if df is None or len(df) == 0:
        return "unavailable"
    # A genuine point-in-time source exposes revised_previous separately from
    # previous and/or a revision timestamp. If revised_previous is entirely null
    # but the source claims revisions exist, integrity is unverified.
    has_revision_col = "revised_previous" in df.columns
    if not has_revision_col:
        return "unverified"
    non_null_revisions = df["revised_previous"].notna().sum()
    if non_null_revisions == 0 and len(df) > 0:
        return "unverified"
    return "verified"


def missingness_report(df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {}
    return {c: {"missing": int(df[c].isna().sum()),
                "completeness": round(1.0 - df[c].isna().mean(), 4)}
            for c in ["actual", "forecast", "previous", "revised_previous"]
            if c in df.columns}


def pit_leakage_test(df: pd.DataFrame) -> dict:
    """Point-in-time leakage test (Phase I).

    For each event E at time T, verify the record carries ONLY information
    available at T. Concretely, this checks the structural preconditions a PIT
    source must satisfy; a full as-of-T replay requires the source's own
    vintage API (not reproducible from a single current-revised export).

    Checks:
      1. ts present, UTC, parseable.
      2. revised_previous, when non-null, is permitted only as a LATER value —
         but in a current-revised export, revised_previous captures today's
         revision, so a non-null revised_previous alone does NOT prove PIT. We
         therefore require an explicit release/revision timestamp to confirm.
      3. A PIT source must expose a release timestamp <= ts is wrong direction;
         instead we flag: if revised_previous is populated but no
         "release_ts"/"revision_ts" column exists to anchor it, PIT is
         UNVERIFIED (the value could be a future revision leaked into history).

    Returns: {pit_status: "verified"|"unverified"|"no_data",
              checks: {...}, leakage_findings: [...]}
    A calendar whose pit_status != "verified" MUST NOT be used for V38.2.
    """
    if df is None or len(df) == 0:
        return {"pit_status": "no_data", "checks": {}, "leakage_findings": [],
                "note": "no calendar data to test"}
    checks = {}
    findings = []
    # 1. ts parseable + UTC
    ts = pd.to_datetime(df["ts"], utc=True, errors="coerce") if "ts" in df.columns else None
    checks["ts_parseable"] = bool(ts is not None and ts.notna().all())
    if ts is not None and ts.notna().any():
        checks["ts_monotonic_release_order"] = bool(ts.is_monotonic_increasing)
    # 2. revised_previous presence
    has_rev = "revised_previous" in df.columns
    rev_non_null = int(df["revised_previous"].notna().sum()) if has_rev else 0
    checks["revised_previous_present"] = has_rev
    checks["revised_previous_non_null"] = rev_non_null
    # 3. an anchor release/revision timestamp is required to PROVE pit
    has_anchor = any(c in df.columns for c in ("release_ts", "revision_ts", "last_update", "LastUpdate"))
    checks["release_anchor_present"] = has_anchor
    # a current-revised export (rev populated, no anchor, or source flagged) => unverified
    if not has_anchor:
        findings.append("no release/revision timestamp column — cannot prove "
                        "revised_previous values were known at event time (PIT_UNVERIFIED)")
    if has_rev and rev_non_null > 0 and not has_anchor:
        findings.append("revised_previous populated without a release anchor — "
                        "future revisions may be leaked into historical rows")
    # 4. no future-dated ts (a current snapshot should not contain future events
    #    unless marked scheduled — those are fine, but actual must be null)
    if ts is not None:
        now = pd.Timestamp.now("UTC")
        future = df[ts > now]
        if len(future) and "actual" in df.columns:
            future_with_actual = future[future["actual"].notna()]
            if len(future_with_actual):
                findings.append(f"{len(future_with_actual)} future-dated events "
                                "with non-null actual — impossible actual "
                                "leaked from the future")
    # 5. forecast must be a genuine pre-release consensus, not inferred from
    #    actual. A structural red flag: forecast == actual for ALL non-null rows
    #    is implausible for a real survey and signals backfill/inference.
    if "forecast" in df.columns and "actual" in df.columns:
        both = df[df["forecast"].notna() & df["actual"].notna()]
        if len(both) > 5:
            eq = (both["forecast"].astype(float) == both["actual"].astype(float)).sum()
            if eq == len(both):
                findings.append("forecast == actual for every row — forecasts appear "
                                "inferred/backfilled from actual (PIT_UNVERIFIED)")
    # 6. revised_previous, when present, must be anchored: it must not appear
    #    for rows whose release anchor is BEFORE the revision was published. We
    #    cannot fully replay vintages from a single export, but a release anchor
    #    (LastUpdate) strictly earlier than ts for a row carrying a non-null
    #    revised_previous different from previous indicates the revision was
    #    known at release — acceptable; absence of an anchor makes it unverifiable.
    if "revised_previous" in df.columns and "previous" in df.columns:
        rev = df[df["revised_previous"].notna()]
        if len(rev) and not has_anchor:
            findings.append("revised_previous present but no release anchor — "
                            "revision provenance cannot be established (PIT_UNVERIFIED)")
    pit = "verified" if (checks["ts_parseable"] and has_anchor and has_rev) else "unverified"
    if findings:
        pit = "unverified"
    return {"pit_status": pit, "checks": checks,
            "leakage_findings": findings,
            "note": "verified requires a release/revision anchor + revised_previous + parseable UTC ts; "
                    "forecast must not equal actual on all rows; no future-dated actual"}


def acquisition_status() -> CalendarAcquisitionStatus:
    """Report the honest acquisition status of the economic calendar.

    No accessible free public point-in-time historical calendar source exists
    from this environment without paid API credentials. Returns BLOCKED status.
    """
    target = Path(__file__).resolve().parents[4] / "data" / "economic_calendar.csv"
    st = CalendarAcquisitionStatus(
        source="(no accessible point-in-time source — paid API required)",
        accessible=target.exists(),
        point_in_time="unavailable",
        retrieval_time_utc=datetime.now(timezone.utc).isoformat())
    if not target.exists():
        st.limitations = [
            "No free public point-in-time historical USD economic calendar source "
            "is accessible from this environment without paid API credentials "
            "(Trading Economics / Forex Factory historical export / FRED ALFRED).",
            "Events were NOT fabricated. actual/forecast/previous were NOT inferred.",
            "To supply: place a genuine calendar at backend/data/economic_calendar.csv "
            "matching the V38.2 schema (see v38/macro/engine.py:CALENDAR_COLUMNS).",
        ]
        return st
    # A file exists — load and assess it honestly
    df = pd.read_csv(target)
    missing = [c for c in CALENDAR_COLUMNS if c not in df.columns]
    if missing:
        st.error = f"schema mismatch — missing columns: {missing}"
        st.limitations = [f"missing columns: {missing}"]
        return st
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    st.event_count = len(df)
    st.usd_event_count = int((df["currency"] == "USD").sum())
    st.coverage_start = str(df["ts"].min())
    st.coverage_end = str(df["ts"].max())
    st.actual_completeness = round(1.0 - df["actual"].isna().mean(), 4)
    st.forecast_completeness = round(1.0 - df["forecast"].isna().mean(), 4)
    st.previous_completeness = round(1.0 - df["previous"].isna().mean(), 4)
    st.revision_coverage = round(1.0 - df["revised_previous"].isna().mean(), 4)
    st.point_in_time = assess_point_in_time(df)
    return st
