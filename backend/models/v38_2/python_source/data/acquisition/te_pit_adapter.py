"""Trading Economics point-in-time calendar ingestion adapter.

This adapter is READY-TO-USE but does NOT fetch anything on its own and does NOT
create `economic_calendar.csv`. It maps the documented Trading Economics
`/economic_calendar/point-in-time` response to the V38.2 schema
(`v38/v38_2/data/schema.py:CALENDAR_COLUMNS`), validates it, and runs the PIT
leakage test. Once an operator supplies an authorized TE PIT export (JSON/CSV)
— obtained with their own paid credentials — calling `ingest_te_pit_file(path)`
produces a validated DataFrame that can be written to
`backend/data/economic_calendar.csv` ONLY after `pit_validation_report()` says
`pit_status == "verified"`.

Nothing here purchases, bypasses a paywall, circumvents an API restriction, or
claims access that is not available. The endpoint is documented publicly; the
data require a paid API key that this adapter never uses directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..schema import CALENDAR_COLUMNS

# Tier-1 USD events the V38.2 macro feature design requires (see
# V38_2_MACRO_EVENT_REQUIREMENTS.md). The adapter preserves ALL rows supplied
# but exposes TIER1_USD_EVENT_KEYS for filtering/validation.
TIER1_USD_EVENTS = (
    "CPI", "Core CPI", "Core Consumer Prices", "Consumer Price Index",
    "Non-Farm Payrolls", "Non Farm Payrolls", "Unemployment Rate",
    "Average Hourly Earnings", "Fed Funds Rate", "Interest Rate",
    "FOMC", "FOMC Statement", "FOMC Meeting Minutes", "FOMC Minutes",
    "GDP", "GDP Growth Rate", "Retail Sales", "Retail Sales MoM",
    "PPI", "Producer Prices",
)

# Trading Economics PIT endpoint documented field -> V38.2 schema column.
TE_PIT_FIELD_MAP = {
    "Date": "ts",                 # release timestamp (TE local/EST -> UTC on ingest)
    "Country": "country",
    "Currency": "currency",
    "Event": "event_name",
    "Category": "category",
    "Importance": "importance",   # numeric 1..3
    "Actual": "actual",
    "Forecast": "forecast",       # consensus survey (pre-release) — PIT
    "TEForecast": "_te_forecast", # TE's own model forecast (kept for audit, not the consensus)
    "Previous": "previous",
    "Revised": "revised_previous",
    "Unit": "unit",
    "LastUpdate": "release_ts",   # PIT anchor: when the record was last updated
    "CalendarId": "_calendar_id",
    "Ticker": "_ticker",
    "ReferenceDate": "_reference_date",
}

# V38.2 directionality is "direct" by default; per-category overrides for USD
# releases where a higher actual is bearish for the priced asset (USD) context.
# This is an editorial label (stable, not a revised value) — PIT_NOT_REQUIRED.
DIRECT_BY_DEFAULT = "direct"


@dataclass
class TEIngestionResult:
    n_rows_in: int = 0
    n_rows_out: int = 0
    n_usd: int = 0
    n_tier1: int = 0
    schema_ok: bool = False
    pit_status: str = "no_data"
    leakage_findings: list = field(default_factory=list)
    missing_fields: dict = field(default_factory=dict)
    coverage_start: Optional[str] = None
    coverage_end: Optional[str] = None
    forecast_completeness: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


def _coerce_float(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if pd.isna(f) or np.isinf(f):
        return None
    return f


def _normalize_te_rows(rows: list) -> pd.DataFrame:
    """Map TE PIT rows -> V38.2 schema DataFrame. UTC timestamps."""
    mapped = []
    for r in rows:
        row = {}
        for te_key, v38_key in TE_PIT_FIELD_MAP.items():
            if te_key in r:
                row[v38_key] = r[te_key]
        mapped.append(row)
    df = pd.DataFrame(mapped)
    if df.empty:
        return df
    # ts: TE returns "yyyy-mm-dd HH:mm[:ss]" in market local time (typically EST/UTC).
    # Treat naive as UTC; if tz-aware, convert to UTC. Never invent a timezone.
    df["ts"] = pd.to_datetime(df.get("ts"), errors="coerce", utc=True)
    # release anchor
    if "release_ts" in df.columns:
        df["release_ts"] = pd.to_datetime(df["release_ts"], errors="coerce", utc=True)
    # numeric coercion
    for c in ("actual", "forecast", "previous", "revised_previous", "importance"):
        if c in df.columns:
            df[c] = df[c].apply(_coerce_float) if c != "importance" else df[c].apply(_coerce_float)
    # importance int 0..3
    if "importance" in df.columns:
        df["importance"] = df["importance"].fillna(1).astype(int).clip(0, 3)
    # currency/country defaults
    df["currency"] = df.get("currency", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    df["country"] = df.get("country", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    df["event_name"] = df.get("event_name", pd.Series(dtype=str)).fillna("").astype(str)
    df["category"] = df.get("category", pd.Series(dtype=str)).fillna("other").astype(str).str.lower()
    df["unit"] = df.get("unit", pd.Series(dtype=str)).fillna("").astype(str)
    df["directionality"] = DIRECT_BY_DEFAULT
    # drop rows without a valid release timestamp (PIT unverifiable)
    df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    # keep audit cols separate; only emit CALENDAR_COLUMNS (+ release_ts anchor)
    keep = [c for c in (CALENDAR_COLUMNS + ["release_ts"]) if c in df.columns]
    return df[keep]


def ingest_te_pit_file(path) -> "tuple[pd.DataFrame, TEIngestionResult]":
    """Load an authorized TE PIT export (JSON list-of-rows or CSV) and map to
    the V38.2 schema. Returns (mapped_df, result). Does NOT write any file.
    """
    p = Path(path)
    res = TEIngestionResult()
    try:
        if p.suffix.lower() == ".json":
            rows = json.loads(p.read_text())
            if isinstance(rows, dict):
                rows = rows.get("results", rows.get("data", rows.get("events", [])))
        else:
            rows = pd.read_csv(p).to_dict("records")
    except Exception as e:
        res.error = f"failed to read {path}: {e}"
        return pd.DataFrame(), res
    res.n_rows_in = len(rows)
    df = _normalize_te_rows(rows)
    res.n_rows_out = len(df)
    if df.empty:
        res.error = "no valid rows after mapping (check TE field names / timestamps)"
        return df, res
    # schema check against required calendar columns
    missing = [c for c in CALENDAR_COLUMNS if c not in df.columns]
    res.schema_ok = not missing
    if missing:
        res.error = f"schema mismatch after mapping — missing: {missing}"
        return df, res
    res.n_usd = int((df["currency"].str.upper() == "USD").sum())
    res.coverage_start = str(df["ts"].min())
    res.coverage_end = str(df["ts"].max())
    res.forecast_completeness = round(1.0 - df["forecast"].isna().mean(), 4)
    res.missing_fields = {
        c: int(df[c].isna().sum()) for c in
        ("actual", "forecast", "previous", "revised_previous") if c in df.columns
    }
    # tier-1 USD presence check (substring match against event_name)
    ev = df["event_name"].str.lower()
    res.n_tier1 = int(ev.str.contains("|".join(k.lower() for k in TIER1_USD_EVENTS)).sum())
    # PIT leakage test — require the release anchor
    from .calendar import pit_leakage_test
    test_df = df.copy()
    rpt = pit_leakage_test(test_df)
    res.pit_status = rpt["pit_status"]
    res.leakage_findings = rpt["leakage_findings"]
    return df, res


def pit_validation_report(df: pd.DataFrame) -> dict:
    """Full PIT validation report for a mapped calendar DataFrame.

    A calendar may be written to backend/data/economic_calendar.csv ONLY when
    this returns pit_status == "verified".
    """
    from .calendar import pit_leakage_test, missingness_report
    base = pit_leakage_test(df)
    return {
        "pit_status": base["pit_status"],
        "checks": base["checks"],
        "leakage_findings": base["leakage_findings"],
        "missingness": missingness_report(df),
        "schema_columns": list(df.columns),
        "n_rows": int(len(df)),
        "may_ingest": base["pit_status"] == "verified",
        "note": "forecast-dependent features require pit_status==verified AND "
                "forecast completeness > 0 (genuine consensus, not inferred).",
    }


def write_validated_calendar(df: pd.DataFrame, dest) -> dict:
    """Write the validated calendar to `dest` ONLY if PIT-verified.

    Refuses to write if pit_status != 'verified' or forecast is entirely missing.
    This is the single chokepoint that prevents non-PIT data from reaching the
    readiness gate.
    """
    rpt = pit_validation_report(df)
    if not rpt["may_ingest"]:
        return {"written": False, "reason": f"PIT not verified: {rpt['leakage_findings']}",
                "report": rpt}
    if rpt["missingness"].get("forecast", {}).get("missing", 1) == rpt["n_rows"]:
        return {"written": False, "reason": "forecast entirely missing — cannot populate "
                "forecast-dependent features without look-ahead", "report": rpt}
    out = Path(dest)
    df.to_csv(out, index=False)
    return {"written": True, "path": str(out), "rows": rpt["n_rows"], "report": rpt}
