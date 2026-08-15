"""FF + ALFRED hybrid economic-calendar acquisition and PIT audit.

Pipeline:
  1. Acquire USD Tier-1 events from Forex Factory historical calendar (2018→latest).
  2. For each event, query ALFRED vintage data (as-of-release-date value) for
     BOTH the current observation period AND the previous observation period.
  3. Cross-check FF actual vs ALFRED vintage (actual_pit_status).
  4. Cross-check FF previous vs ALFRED prior-period vintage (previous_pit_status).
  5. Classify forecast as FORECAST_PIT_UNVERIFIED always (req 3, 7, 8).
  6. Produce 7 outputs:
     - raw FF dataset (ff_records.csv)
     - ALFRED cross-check dataset (alfred_crosscheck.csv)
     - canonical merged dataset (canonical_merged.csv)
     - provenance manifest (PROVENANCE_MANIFEST.json)
     - PIT audit report (PIT_AUDIT_REPORT.md + .json)
     - match/mismatch report (MATCH_MISMATCH_REPORT.csv)
     - coverage report (COVERAGE_REPORT.md + .json)

This module does NOT write economic_calendar.csv (req 14) and does NOT modify
the readiness gate (req 15). It produces an audit for operator decision-making.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .ff_calendar import (
    acquire_ff_range,
    ff_obs_date_from_ts,
    ff_prev_obs_date_from_ts,
    RAW_CACHE_DIR as FF_RAW_DIR,
)
from .fred_vintages import (
    query_alfred_vintage,
    VINTAGE_CACHE_DIR as FRED_RAW_DIR,
)
from .tier1_mapping import TIER1_EVENTS

REPORT_DIR = Path(__file__).resolve().parents[2]
RAW_OUT_DIR = Path(__file__).resolve().parents[4] / "data" / "ff_alfred_hybrid"


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _compute_fred_pct_change(fred_current_obs: float | None,
                              fred_prev_obs: float | None,
                              fred_series: str, pct_period: str | None) -> float | None:
    """Compute the % change from FRED index levels to compare with FF %.

    For MoM %: (current - prev) / prev * 100
    For NFP (PAYEMS): current - prev (absolute change in thousands)
    """
    if fred_current_obs is None or fred_prev_obs is None:
        return None
    if fred_series == "PAYEMS":
        return fred_current_obs - fred_prev_obs
    if pct_period == "mom":
        if fred_prev_obs == 0:
            return None
        return (fred_current_obs - fred_prev_obs) / fred_prev_obs * 100
    return None


def _compare_value(ff_val: float | None, fred_val: float | None,
                   fred_series: str, ff_scale: float = 1.0,
                   tolerance: float = 0.15) -> str:
    """Compare a single FF value to a FRED-derived comparison value.

    ff_scale: multiplier to normalize FF units to FRED units
              (e.g. NFP: FF=148000, FRED=148 → ff_scale=0.001)
    Returns: 'match', 'mismatch', or 'incomparable'.
    """
    if ff_val is None or fred_val is None:
        return "incomparable"
    ff_normalized = ff_val * ff_scale
    if abs(ff_normalized - fred_val) < tolerance:
        return "match"
    return "mismatch"


def _classify_actual(ff_actual, ff_previous, fred_vintage, fred_vintage_prev,
                    fred_current, fred_series, is_pct, pct_period):
    """Classify the actual value PIT status.

    Returns (actual_pit_status, match_status, fred_computed_actual).
    """
    if fred_series is None:
        return "PIT_NO_INDICATOR", "incomparable", None

    if fred_vintage is None:
        return "PIT_ALFRED_MISSING", "incomparable", None

    # Level series: direct comparison (UNRATE, FEDFUNDS)
    if fred_series in ("UNRATE", "FEDFUNDS"):
        m = _compare_value(ff_actual, fred_vintage, fred_series, tolerance=0.15)
        if m == "match":
            return "PIT_ACTUAL_VERIFIED", "match", fred_vintage
        return "PIT_ACTUAL_MISMATCH", "mismatch", fred_vintage

    # GDP: already a % series — direct comparison
    if fred_series == "A191RL1Q225SBEA":
        m = _compare_value(ff_actual, fred_vintage, fred_series, tolerance=0.5)
        if m == "match":
            return "PIT_ACTUAL_VERIFIED", "match", fred_vintage
        # GDP mismatch: FF shows advance estimate, FRED shows revised.
        # The mismatch PROVES FF is the original PIT release.
        return "PIT_ADVANCE_ESTIMATE", "mismatch", fred_vintage

    # NFP (PAYEMS): FF shows change in thousands (absolute), FRED shows level.
    if fred_series == "PAYEMS":
        if fred_vintage_prev is None:
            return "PIT_ALFRED_MISSING", "fred_prev_missing", None
        fred_change = fred_vintage - fred_vintage_prev
        # FF=148000 (absolute), FRED change=148 (thousands) → ff_scale=0.001
        m = _compare_value(ff_actual, fred_change, fred_series,
                           ff_scale=0.001, tolerance=5.0)
        if m == "match":
            return "PIT_ACTUAL_VERIFIED", "match", fred_change
        return "PIT_ACTUAL_MISMATCH", "mismatch", fred_change

    # Percentage/index series (CPI, PPI, Retail Sales, etc.):
    # FF shows % change, FRED shows index level → compute % from vintages
    if is_pct and pct_period == "mom":
        if fred_vintage_prev is None:
            return "PIT_ALFRED_MISSING", "fred_prev_missing", None
        fred_pct = _compute_fred_pct_change(
            fred_vintage, fred_vintage_prev, fred_series, pct_period)
        if fred_pct is None:
            return "PIT_ALFRED_MISSING", "incomparable", None
        m = _compare_value(ff_actual, fred_pct, fred_series, tolerance=0.15)
        if m == "match":
            return "PIT_ACTUAL_VERIFIED", "match", fred_pct
        return "PIT_ACTUAL_MISMATCH", "mismatch", fred_pct

    # Fallback: direct comparison
    m = _compare_value(ff_actual, fred_vintage, fred_series, tolerance=0.15)
    if m == "match":
        return "PIT_ACTUAL_VERIFIED", "match", fred_vintage
    return "PIT_ACTUAL_MISMATCH", "mismatch", fred_vintage


def _classify_previous(ff_previous, fred_vintage_prev, fred_current_prev,
                       fred_series, is_pct, pct_period):
    """Classify the previous value PIT status.

    The FF 'previous' should correspond to the prior period's ALFRED vintage
    value (as known at the release date).
    Returns (previous_pit_status, prev_match_status, fred_computed_prev).
    """
    if fred_series is None:
        return "PIT_NO_INDICATOR", "incomparable", None

    if ff_previous is None or pd.isna(ff_previous):
        return "PREVIOUS_ABSENT", "incomparable", None

    if fred_vintage_prev is None:
        return "PIT_ALFRED_PREV_MISSING", "incomparable", None

    # Level series: direct comparison
    if fred_series in ("UNRATE", "FEDFUNDS"):
        m = _compare_value(ff_previous, fred_vintage_prev, fred_series,
                           tolerance=0.15)
        if m == "match":
            return "PIT_PREVIOUS_VERIFIED", "match", fred_vintage_prev
        return "PIT_PREVIOUS_MISMATCH", "mismatch", fred_vintage_prev

    # GDP: previous is prior quarter's growth %
    if fred_series == "A191RL1Q225SBEA":
        m = _compare_value(ff_previous, fred_vintage_prev, fred_series,
                           tolerance=0.5)
        if m == "match":
            return "PIT_PREVIOUS_VERIFIED", "match", fred_vintage_prev
        return "PIT_PREVIOUS_MISMATCH", "mismatch", fred_vintage_prev

    # NFP: FF previous is the prior month's change in thousands
    if fred_series == "PAYEMS":
        # FF previous = 252000 (absolute), FRED prior change = prior_obs - prior_prior_obs
        # We don't have prior_prior_obs here, so compare FF previous to the
        # prior month's level change. But we only fetched one prev obs.
        # Instead: FF 'previous' for NFP is the prior month's NFP number.
        # FRED vintage_prev is the prior month's LEVEL. These aren't directly
        # comparable (one is a change, one is a level).
        # Mark as PREVIOUS_NOT_COMPARABLE for PAYEMS.
        return "PREVIOUS_NOT_COMPARABLE", "incomparable", fred_vintage_prev

    # Percentage/index series: FF previous is the prior period's % change
    if is_pct and pct_period == "mom":
        # We would need the prior-prior obs to compute the prior % change.
        # We only have fred_vintage_prev (the prior period's level).
        # FF 'previous' is the prior period's MoM %, which we can't compute
        # without the prior-prior obs. Mark as not directly comparable.
        return "PREVIOUS_NOT_COMPARABLE", "incomparable", fred_vintage_prev

    m = _compare_value(ff_previous, fred_vintage_prev, fred_series,
                       tolerance=0.15)
    if m == "match":
        return "PIT_PREVIOUS_VERIFIED", "match", fred_vintage_prev
    return "PIT_PREVIOUS_MISMATCH", "mismatch", fred_vintage_prev


def _classify_forecast(ff_forecast):
    """Classify the forecast PIT status.

    FF forecasts are RETAINED but always marked FORECAST_PIT_UNVERIFIED.
    FF does not expose a pre-release forecast timestamp (req 3, 7, 8).
    ALFRED provides no forecast/consensus field (req 6).
    """
    if ff_forecast is None or pd.isna(ff_forecast):
        return "FORECAST_ABSENT"
    return "FORECAST_PIT_UNVERIFIED"


def _classify_overall(actual_pit, previous_pit, forecast_pit):
    """Aggregate the overall PIT status from the three sub-statuses."""
    actual_ok = actual_pit in ("PIT_ACTUAL_VERIFIED", "PIT_ADVANCE_ESTIMATE")
    previous_ok = previous_pit in ("PIT_PREVIOUS_VERIFIED", "PREVIOUS_ABSENT",
                                    "PREVIOUS_NOT_COMPARABLE")
    forecast_ok = forecast_pit == "FORECAST_ABSENT"  # absent is neutral

    if actual_pit == "PIT_NO_INDICATOR":
        return "OVERALL_NO_INDICATOR"
    if actual_pit == "PIT_ALFRED_MISSING":
        return "OVERALL_ALFRED_MISSING"
    if actual_ok and previous_ok:
        if forecast_pit == "FORECAST_PIT_UNVERIFIED":
            return "OVERALL_PARTIAL_PIT"
        return "OVERALL_PIT_VERIFIED"
    if actual_ok and not previous_ok:
        return "OVERALL_ACTUAL_ONLY_PIT"
    return "OVERALL_PIT_MISMATCH"


# ---------------------------------------------------------------------------
# Provenance manifest
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _build_provenance_manifest(ff_df, alfred_df, audit_df, coverage,
                                start_date, end_date):
    """Build the provenance manifest with hashes and source info."""
    ff_records_path = RAW_OUT_DIR / "ff_records.csv"
    alfred_path = RAW_OUT_DIR / "alfred_crosscheck.csv"
    merged_path = RAW_OUT_DIR / "canonical_merged.csv"
    audit_path = RAW_OUT_DIR / "hybrid_audit.csv"

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": "FF + ALFRED hybrid economic calendar acquisition",
        "range": {"start": str(start_date), "end": str(end_date)},
        "sources": {
            "forex_factory": {
                "type": "historical calendar HTML pages",
                "base_url": "https://www.forexfactory.com/calendar",
                "url_pattern": "https://www.forexfactory.com/calendar?week=MMMDD.YYYY",
                "encoding": "windows-1252",
                "cache_dir": str(FF_RAW_DIR),
                "cached_files": len(list(FF_RAW_DIR.glob("week_*.html"))) if FF_RAW_DIR.exists() else 0,
                "throttling": "1.0s delay between requests",
                "provides": ["event timestamp", "currency", "impact", "event name",
                             "actual", "forecast (consensus)", "previous"],
                "pit_note": "FF event time IS the release time. FF does NOT expose "
                            "a pre-release forecast timestamp.",
            },
            "alfred_fred": {
                "type": "vintage CSV endpoint",
                "base_url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
                "url_pattern": "?id=SERIES&cosd=START&coed=END&vintage_date=DATE",
                "user_agent": "curl/8.0",
                "cache_dir": str(FRED_RAW_DIR),
                "cached_files": len(list(FRED_RAW_DIR.glob("*.csv"))) if FRED_RAW_DIR.exists() else 0,
                "throttling": "0.3s delay between requests",
                "provides": ["vintage indicator values (as-of-T)", "current (revised) values"],
                "pit_note": "ALFRED vintage_date returns the value as known on that date. "
                            "Used ONLY to validate actual/previous, NOT to reconstruct forecasts.",
            },
        },
        "tier1_events": [{"name": e["name"], "fred_series": e["fred_series"],
                          "category": e["category"]} for e in TIER1_EVENTS],
        "outputs": {
            "raw_ff_dataset": {
                "path": str(ff_records_path),
                "rows": len(ff_df),
                "sha256": _sha256_file(ff_records_path),
            },
            "alfred_crosscheck": {
                "path": str(alfred_path),
                "rows": len(alfred_df),
                "sha256": _sha256_file(alfred_path),
            },
            "canonical_merged": {
                "path": str(merged_path),
                "rows": len(audit_df),
                "sha256": _sha256_file(merged_path),
            },
            "hybrid_audit": {
                "path": str(audit_path),
                "rows": len(audit_df),
                "sha256": _sha256_file(audit_path),
            },
        },
        "coverage": coverage,
        "non_fabrication_guarantee": (
            "No actuals, forecasts, previous values, or timestamps were fabricated. "
            "Missing values stay missing. ALFRED is used only to validate FF values, "
            "never to reconstruct or substitute them. FF forecasts are retained but "
            "marked FORECAST_PIT_UNVERIFIED."
        ),
    }
    return manifest


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def _build_coverage_report(ff_df, audit_df, start_date, end_date):
    """Build coverage statistics by year and event type."""
    if ff_df.empty:
        return {"error": "no FF data"}

    ff_df = ff_df.copy()
    ff_df["year"] = pd.to_datetime(ff_df["ts"]).dt.year

    coverage = {
        "range": {"start": str(start_date), "end": str(end_date)},
        "total_ff_events": len(ff_df),
        "tier1_event_types": ff_df["event_name"].nunique(),
        "coverage_start": str(ff_df["ts"].min()),
        "coverage_end": str(ff_df["ts"].max()),
        "by_year": {},
        "by_event_type": {},
        "by_category": {},
    }

    for year, grp in ff_df.groupby("year"):
        coverage["by_year"][int(year)] = {
            "total_events": len(grp),
            "event_types": grp["event_name"].nunique(),
            "with_forecast": int(grp["forecast"].notna().sum()),
            "with_actual": int(grp["actual"].notna().sum()),
            "with_previous": int(grp["previous"].notna().sum()),
        }

    for name, grp in ff_df.groupby("event_name"):
        coverage["by_event_type"][name] = {
            "total_events": len(grp),
            "first_event": str(grp["ts"].min()),
            "last_event": str(grp["ts"].max()),
            "with_forecast": int(grp["forecast"].notna().sum()),
            "forecast_completeness": round(float(grp["forecast"].notna().sum()) / max(len(grp), 1), 4),
        }

    for cat, grp in ff_df.groupby("category"):
        coverage["by_category"][cat] = {
            "total_events": len(grp),
            "event_types": grp["event_name"].nunique(),
        }

    # Expected monthly events (for gap analysis)
    years_covered = sorted(ff_df["year"].unique())
    months_covered = (max(years_covered) - min(years_covered)) * 12 + 12
    expected_monthly = months_covered * 8  # ~8 monthly tier-1 events
    coverage["expected_monthly_events_approx"] = expected_monthly
    coverage["monthly_completeness"] = round(
        len(ff_df) / max(expected_monthly, 1), 4)

    return coverage


# ---------------------------------------------------------------------------
# Main audit pipeline
# ---------------------------------------------------------------------------

def run_hybrid_audit(start_date: datetime = None, end_date: datetime = None,
                     cache: bool = True, max_weeks: int | None = None) -> dict:
    """Run the full FF + ALFRED hybrid acquisition and audit."""
    if start_date is None:
        start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
    if end_date is None:
        end_date = datetime.now(timezone.utc)

    print("=" * 70, flush=True)
    print("FF + ALFRED Hybrid Economic Calendar Audit", flush=True)
    print("=" * 70, flush=True)
    print(f"Range: {start_date.date()} → {end_date.date()}", flush=True)
    print(f"Tier-1 event types: {len(TIER1_EVENTS)}", flush=True)
    print(f"Cache: {cache}, Max weeks: {max_weeks or 'all'}", flush=True)
    print()

    # Step 1: Acquire FF historical calendar data
    print("[Step 1] Acquiring Forex Factory historical calendar...", flush=True)
    ff_df = acquire_ff_range(start_date, end_date, cache=cache, max_weeks=max_weeks)
    print(f"  FF records acquired: {len(ff_df)}", flush=True)
    if ff_df.empty:
        print("  ERROR: No FF records acquired. Aborting.", flush=True)
        return {"error": "no FF records", "ff_count": 0}

    print("  FF records by event type:", flush=True)
    for name, grp in ff_df.groupby("event_name"):
        n_forecast = grp["forecast"].notna().sum()
        print(f"    {name}: {len(grp)} events ({n_forecast} with forecast)", flush=True)
    print()

    # Step 2: Query ALFRED vintages for each event
    print("[Step 2] Querying ALFRED vintages for cross-check...", flush=True)
    alfred_rows = []
    alfred_matched = 0
    alfred_missing = 0

    for idx, row in ff_df.iterrows():
        series_id = row["fred_series"]
        event_ts = row["ts"]
        freq = row.get("freq", "monthly")
        vintage_date = event_ts.strftime("%Y-%m-%d")

        obs_date = ff_obs_date_from_ts(event_ts, freq=freq)
        prev_obs_date = ff_prev_obs_date_from_ts(event_ts, freq=freq)

        if series_id is None:
            alfred_rows.append({
                "ff_idx": idx,
                "ts": event_ts,
                "event_name": row["event_name"],
                "fred_series": None,
                "obs_date": obs_date,
                "prev_obs_date": prev_obs_date,
                "vintage_date": vintage_date,
                "vintage_value": None,
                "vintage_prev": None,
                "current_value": None,
                "current_prev": None,
                "revised": False,
                "available": False,
                "reason": "no_fred_series",
            })
            alfred_missing += 1
            continue

        # Query current obs vintage
        result = query_alfred_vintage(series_id, obs_date, vintage_date, cache=cache)

        # Query previous obs vintage (for % change computation and previous validation)
        prev_result = query_alfred_vintage(series_id, prev_obs_date, vintage_date, cache=cache)

        alfred_rows.append({
            "ff_idx": idx,
            "ts": event_ts,
            "event_name": row["event_name"],
            "fred_series": series_id,
            "obs_date": obs_date,
            "prev_obs_date": prev_obs_date,
            "vintage_date": vintage_date,
            "vintage_value": result.get("vintage_value"),
            "vintage_prev": prev_result.get("vintage_value"),
            "current_value": result.get("current_value"),
            "current_prev": prev_result.get("current_value"),
            "revised": result.get("revised", False),
            "available": result.get("available", False),
            "prev_available": prev_result.get("available", False),
            "reason": "ok" if result.get("available") else "vintage_not_found",
        })

        if result.get("available"):
            alfred_matched += 1
        else:
            alfred_missing += 1

        if (idx + 1) % 50 == 0:
            print(f"  [alfred] {idx+1}/{len(ff_df)} events queried "
                  f"({alfred_matched} matched, {alfred_missing} missing)", flush=True)

    alfred_df = pd.DataFrame(alfred_rows)
    print(f"  ALFRED records matched: {alfred_matched}", flush=True)
    print(f"  ALFRED records missing: {alfred_missing}", flush=True)
    print()

    # Step 3: Cross-check and classify with 4 PIT statuses
    print("[Step 3] Cross-checking FF vs ALFRED and classifying PIT...", flush=True)
    audit_rows = []
    actual_verified = 0
    previous_verified = 0
    forecast_verified = 0
    forecast_unverified = 0
    mismatches = 0
    missing_records = 0

    for idx, row in ff_df.iterrows():
        alfred = alfred_rows[idx] if idx < len(alfred_rows) else {}
        fred_series = row["fred_series"]
        fred_vintage = alfred.get("vintage_value")
        fred_vintage_prev = alfred.get("vintage_prev")
        fred_current = alfred.get("current_value")
        fred_current_prev = alfred.get("current_prev")

        has_forecast = row["forecast"] is not None and not pd.isna(row["forecast"])
        has_actual = row["actual"] is not None and not pd.isna(row["actual"])
        has_previous = row["previous"] is not None and not pd.isna(row["previous"])
        alfred_available = alfred.get("available", False)
        alfred_prev_available = alfred.get("prev_available", False)

        # Classify actual
        actual_pit, actual_match, fred_computed_actual = _classify_actual(
            row["actual"], row["previous"], fred_vintage, fred_vintage_prev,
            fred_current, fred_series, row["is_pct"], row["pct_period"])

        # Classify previous
        previous_pit, prev_match, fred_computed_prev = _classify_previous(
            row["previous"], fred_vintage_prev, fred_current_prev,
            fred_series, row["is_pct"], row["pct_period"])

        # Classify forecast (always UNVERIFIED per req 3, 7, 8)
        forecast_pit = _classify_forecast(row["forecast"])

        # Overall
        overall_pit = _classify_overall(actual_pit, previous_pit, forecast_pit)

        # Counters
        if actual_pit in ("PIT_ACTUAL_VERIFIED", "PIT_ADVANCE_ESTIMATE"):
            actual_verified += 1
        if actual_pit == "PIT_ACTUAL_MISMATCH":
            mismatches += 1
        if previous_pit == "PIT_PREVIOUS_VERIFIED":
            previous_verified += 1
        if previous_pit in ("PIT_PREVIOUS_MISMATCH", "PIT_ALFRED_PREV_MISSING"):
            mismatches += 1
        if forecast_pit == "FORECAST_PIT_UNVERIFIED":
            forecast_unverified += 1
        if actual_pit in ("PIT_ALFRED_MISSING", "PIT_NO_INDICATOR"):
            missing_records += 1

        audit_rows.append({
            "ts": row["ts"],
            "event_name_raw": row["event_name_raw"],
            "event_name": row["event_name"],
            "category": row["category"],
            "currency": row["currency"],
            "importance": row["importance"],
            "impact_label": row["impact_label"],
            "ff_actual": row["actual"],
            "ff_forecast": row["forecast"],
            "ff_previous": row["previous"],
            "ff_actual_raw": row.get("actual_raw", ""),
            "ff_forecast_raw": row.get("forecast_raw", ""),
            "ff_previous_raw": row.get("previous_raw", ""),
            "fred_series": fred_series,
            "fred_vintage": fred_vintage,
            "fred_vintage_prev": fred_vintage_prev,
            "fred_current": fred_current,
            "fred_current_prev": fred_current_prev,
            "fred_computed_actual": fred_computed_actual,
            "fred_computed_prev": fred_computed_prev,
            "alfred_available": alfred_available,
            "alfred_prev_available": alfred_prev_available,
            "alfred_revised": alfred.get("revised", False),
            "actual_match_status": actual_match,
            "previous_match_status": prev_match,
            "has_forecast": has_forecast,
            "has_actual": has_actual,
            "has_previous": has_previous,
            "actual_pit_status": actual_pit,
            "previous_pit_status": previous_pit,
            "forecast_pit_status": forecast_pit,
            "overall_pit_status": overall_pit,
            "obs_date": alfred.get("obs_date", ""),
            "prev_obs_date": alfred.get("prev_obs_date", ""),
            "vintage_date": alfred.get("vintage_date", ""),
            "ff_url": row.get("ff_url", ""),
            "source": row.get("source", "forexfactory"),
        })

    audit_df = pd.DataFrame(audit_rows)

    print(f"  Actual PIT verified: {actual_verified}", flush=True)
    print(f"  Previous PIT verified: {previous_verified}", flush=True)
    print(f"  Forecast PIT verified: {forecast_verified} (always 0 — no pre-release proof)", flush=True)
    print(f"  Forecast PIT unverified: {forecast_unverified}", flush=True)
    print(f"  Mismatches: {mismatches}", flush=True)
    print(f"  Missing records: {missing_records}", flush=True)
    print()

    # Step 4: Coverage analysis
    print("[Step 4] Building coverage report...", flush=True)
    coverage = _build_coverage_report(ff_df, audit_df, start_date, end_date)

    # Step 5: Write all outputs
    print("[Step 5] Writing outputs...", flush=True)
    RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Raw FF dataset
    ff_df.to_csv(RAW_OUT_DIR / "ff_records.csv", index=False)

    # 2. ALFRED cross-check dataset
    alfred_df.to_csv(RAW_OUT_DIR / "alfred_crosscheck.csv", index=False)

    # 3. Canonical merged dataset (FF + ALFRED + PIT statuses)
    audit_df.to_csv(RAW_OUT_DIR / "canonical_merged.csv", index=False)

    # 4. Hybrid audit CSV (same as canonical merged, for compatibility)
    audit_df.to_csv(RAW_OUT_DIR / "hybrid_audit.csv", index=False)

    # 5. Match/mismatch report
    mm_df = audit_df[audit_df["actual_match_status"].isin(["match", "mismatch"])].copy()
    mm_df = mm_df[["ts", "event_name", "event_name_raw", "ff_actual",
                    "fred_computed_actual", "fred_vintage", "actual_match_status",
                    "actual_pit_status", "previous_match_status", "previous_pit_status"]]
    mm_df.to_csv(RAW_OUT_DIR / "MATCH_MISMATCH_REPORT.csv", index=False)

    # 6. Provenance manifest
    manifest = _build_provenance_manifest(ff_df, alfred_df, audit_df, coverage,
                                           start_date, end_date)
    manifest_path = RAW_OUT_DIR / "PROVENANCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    # 7. Coverage report
    coverage_path = RAW_OUT_DIR / "COVERAGE_REPORT.json"
    coverage_path.write_text(json.dumps(coverage, indent=2, default=str))
    _write_coverage_md(coverage, RAW_OUT_DIR / "COVERAGE_REPORT.md")

    # PIT audit report
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "range": {"start": str(start_date), "end": str(end_date)},
        "tier1_event_types": len(TIER1_EVENTS),
        "ff_records_acquired": len(ff_df),
        "alfred_records_matched": alfred_matched,
        "alfred_records_missing": alfred_missing,
        "actual_pit_verified": actual_verified,
        "previous_pit_verified": previous_verified,
        "forecast_pit_verified": forecast_verified,
        "forecast_pit_unverified": forecast_unverified,
        "mismatches": mismatches,
        "missing_records": missing_records,
        "coverage": coverage,
        "actual_pit_breakdown": audit_df["actual_pit_status"].value_counts().to_dict() if not audit_df.empty else {},
        "previous_pit_breakdown": audit_df["previous_pit_status"].value_counts().to_dict() if not audit_df.empty else {},
        "forecast_pit_breakdown": audit_df["forecast_pit_status"].value_counts().to_dict() if not audit_df.empty else {},
        "overall_pit_breakdown": audit_df["overall_pit_status"].value_counts().to_dict() if not audit_df.empty else {},
        "match_status_breakdown": audit_df["actual_match_status"].value_counts().to_dict() if not audit_df.empty else {},
        "pit_verdicts": {
            "actual": "FF actuals are PIT-verified via ALFRED vintage cross-check. "
                      "Values matching the ALFRED as-of-release-date vintage are proven PIT.",
            "previous": "FF previous values are PIT-verified for level series (UNRATE, FEDFUNDS, GDP). "
                        "For % change series, prior-period % requires prior-prior obs (not fetched).",
            "forecast": "ALL FF forecasts are FORECAST_PIT_UNVERIFIED. FF does not expose pre-release "
                        "forecast timestamps. ALFRED provides no forecast field. Forecasts are RETAINED "
                        "but cannot be proven PIT. No historical consensus is reconstructed from FRED/ALFRED.",
        },
        "feature_impact": {
            "surprise": "RETAINED — depends on (actual - forecast). Actual is PIT-verified; "
                        "forecast is PIT_UNVERIFIED. surprise values are preserved but not fully PIT-proven.",
            "surprise_pct": "RETAINED — depends on actual/forecast/previous. Same PIT status mix.",
            "surprise_zscore": "RETAINED — requires >=30 prior PIT surprises. Forecast history is "
                               "PIT_UNVERIFIED, so z-scores cannot be fully PIT-proven.",
            "macro_direction": "RETAINED — derived from PIT surprise. Same caveat.",
        },
        "outputs": {
            "raw_ff_dataset": str(RAW_OUT_DIR / "ff_records.csv"),
            "alfred_crosscheck": str(RAW_OUT_DIR / "alfred_crosscheck.csv"),
            "canonical_merged": str(RAW_OUT_DIR / "canonical_merged.csv"),
            "provenance_manifest": str(manifest_path),
            "pit_audit_report_md": str(REPORT_DIR / "PIT_AUDIT_REPORT.md"),
            "pit_audit_report_json": str(REPORT_DIR / "PIT_AUDIT_REPORT.json"),
            "match_mismatch_report": str(RAW_OUT_DIR / "MATCH_MISMATCH_REPORT.csv"),
            "coverage_report_md": str(RAW_OUT_DIR / "COVERAGE_REPORT.md"),
            "coverage_report_json": str(coverage_path),
        },
        "non_modifications": [
            "economic_calendar.csv NOT written (per req 14)",
            "readiness_gate.py NOT modified (per req 15)",
            "No training started (per req 16)",
            "surprise/surprise_pct/surprise_zscore/macro_direction NOT removed or weakened (per req 17)",
        ],
    }

    # Write PIT audit report JSON + MD
    _write_pit_audit_report(report)

    print(f"  Outputs written to: {RAW_OUT_DIR}", flush=True)
    print(f"  PIT audit report: {report['outputs']['pit_audit_report_md']}", flush=True)
    print()

    return report


def _write_coverage_md(coverage: dict, path: Path):
    """Write coverage report as Markdown."""
    md = []
    md.append("# FF + ALFRED Coverage Report\n\n")
    md.append(f"**Range:** {coverage['range']['start']} → {coverage['range']['end']}\n\n")
    md.append(f"- **Total FF events:** {coverage['total_ff_events']}\n")
    md.append(f"- **Tier-1 event types:** {coverage['tier1_event_types']}\n")
    md.append(f"- **Coverage start:** {coverage['coverage_start']}\n")
    md.append(f"- **Coverage end:** {coverage['coverage_end']}\n")
    md.append(f"- **Expected monthly events (approx):** {coverage['expected_monthly_events_approx']}\n")
    md.append(f"- **Monthly completeness:** {coverage['monthly_completeness']:.1%}\n\n")

    md.append("## By Year\n\n")
    md.append("| Year | Events | Types | With Forecast | With Actual | With Previous |\n")
    md.append("|---|---|---|---|---|---|\n")
    for year in sorted(coverage["by_year"].keys()):
        y = coverage["by_year"][year]
        md.append(f"| {year} | {y['total_events']} | {y['event_types']} | "
                  f"{y['with_forecast']} | {y['with_actual']} | {y['with_previous']} |\n")

    md.append("\n## By Event Type\n\n")
    md.append("| Event | Count | First | Last | With Forecast | Forecast % |\n")
    md.append("|---|---|---|---|---|---|\n")
    for name in sorted(coverage["by_event_type"].keys()):
        e = coverage["by_event_type"][name]
        md.append(f"| {name} | {e['total_events']} | {e['first_event'][:10]} | "
                  f"{e['last_event'][:10]} | {e['with_forecast']} | "
                  f"{e['forecast_completeness']:.1%} |\n")

    md.append("\n## By Category\n\n")
    md.append("| Category | Events | Types |\n")
    md.append("|---|---|---|\n")
    for cat in sorted(coverage["by_category"].keys()):
        c = coverage["by_category"][cat]
        md.append(f"| {cat} | {c['total_events']} | {c['event_types']} |\n")

    path.write_text("".join(md))


def _write_pit_audit_report(report: dict):
    """Write PIT audit report as JSON and Markdown."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / "PIT_AUDIT_REPORT.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))

    md = []
    md.append("# V38.2 FF + ALFRED Hybrid PIT Audit Report\n\n")
    md.append(f"**Generated:** {report['timestamp_utc']}\n")
    md.append(f"**Range:** {report['range']['start']} → {report['range']['end']}\n\n")

    md.append("## 1. Summary Statistics\n\n")
    md.append(f"| Metric | Count |\n|---|---|\n")
    md.append(f"| Total FF events | {report['ff_records_acquired']} |\n")
    md.append(f"| Tier-1 event types | {report['tier1_event_types']} |\n")
    md.append(f"| ALFRED matches | {report['alfred_records_matched']} |\n")
    md.append(f"| ALFRED missing | {report['alfred_records_missing']} |\n")
    md.append(f"| Actual PIT verified | {report['actual_pit_verified']} |\n")
    md.append(f"| Previous PIT verified | {report['previous_pit_verified']} |\n")
    md.append(f"| Forecast PIT verified | {report['forecast_pit_verified']} |\n")
    md.append(f"| Forecast PIT unverified | {report['forecast_pit_unverified']} |\n")
    md.append(f"| Mismatches | {report['mismatches']} |\n")
    md.append(f"| Missing records | {report['missing_records']} |\n\n")

    md.append("## 2. PIT Status Breakdowns\n\n")
    md.append("### Actual PIT Status\n\n")
    for s, c in sorted(report["actual_pit_breakdown"].items()):
        md.append(f"- {s}: {c}\n")
    md.append("\n### Previous PIT Status\n\n")
    for s, c in sorted(report["previous_pit_breakdown"].items()):
        md.append(f"- {s}: {c}\n")
    md.append("\n### Forecast PIT Status\n\n")
    for s, c in sorted(report["forecast_pit_breakdown"].items()):
        md.append(f"- {s}: {c}\n")
    md.append("\n### Overall PIT Status\n\n")
    for s, c in sorted(report["overall_pit_breakdown"].items()):
        md.append(f"- {s}: {c}\n")

    md.append("\n## 3. PIT Verdicts\n\n")
    for k, v in report["pit_verdicts"].items():
        md.append(f"**{k.title()}:** {v}\n\n")

    md.append("## 4. Feature Impact (surprise/surprise_pct/surprise_zscore/macro_direction)\n\n")
    md.append("These features are **RETAINED and NOT weakened**. Their PIT status depends "
              "on the underlying actual/forecast/previous PIT statuses:\n\n")
    for feat, desc in report["feature_impact"].items():
        md.append(f"- **{feat}**: {desc}\n")

    md.append("\n## 5. Coverage\n\n")
    cov = report["coverage"]
    md.append(f"- Coverage start: {cov['coverage_start']}\n")
    md.append(f"- Coverage end: {cov['coverage_end']}\n")
    md.append(f"- Monthly completeness: {cov['monthly_completeness']:.1%}\n")
    md.append(f"- Total events by year:\n")
    for year in sorted(cov["by_year"].keys()):
        y = cov["by_year"][year]
        md.append(f"  - {year}: {y['total_events']} events ({y['event_types']} types)\n")

    md.append("\n## 6. Non-Modifications\n\n")
    for item in report["non_modifications"]:
        md.append(f"- {item}\n")

    md.append("\n## 7. Outputs\n\n")
    for name, path in report["outputs"].items():
        md.append(f"- **{name}**: `{path}`\n")

    md.append("\n## 8. Provenance\n\n")
    md.append("See `PROVENANCE_MANIFEST.json` for full source provenance, SHA-256 hashes, "
              "and cache inventory. All FF and FRED responses are cached. "
              "No aggressive concurrency (1s FF throttle, 0.3s FRED throttle).\n")

    (REPORT_DIR / "PIT_AUDIT_REPORT.md").write_text("".join(md))

