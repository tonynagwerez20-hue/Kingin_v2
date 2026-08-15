"""Build the V38.2 data manifest — machine-readable inventory with explicit
statuses (AVAILABLE / ABSENT / INVALID / PARTIAL / VALIDATED).

The manifest is the single source of truth for what data is genuinely present.
It never silently substitutes H1 for M5. If a dataset is absent, status=ABSENT.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import V38_2_DIR
from .loader import load_h1, load_h4, load_m5, load_m15
from .calendar_loader import load_calendar
from .schema import CALENDAR_COLUMNS, expected_bars_per_year


def _bar_entry(tf, res) -> dict:
    first_ts = str(res.df["ts"].min()) if res.df is not None and len(res.df) else None
    last_ts = str(res.df["ts"].max()) if res.df is not None and len(res.df) else None
    status = res.status
    if status == "AVAILABLE" and res.validation and res.validation.get("ok"):
        status = "VALIDATED"
    elif status == "AVAILABLE" and res.validation and not res.validation.get("ok"):
        status = "INVALID"
    return {
        "symbol": "XAUUSD", "timeframe": tf, "source_files": res.source_files,
        "source_sha256": res.source_sha256,
        "first_timestamp": first_ts, "last_timestamp": last_ts,
        "row_count": res.row_count,
        "unique_timestamp_count": res.row_count if status in ("VALIDATED", "AVAILABLE") else 0,
        "duplicate_count": res.validation["duplicate_ts_count"] if res.validation else 0,
        "nan_count": res.validation["nan_count"] if res.validation else 0,
        "inf_count": res.validation["inf_count"] if res.validation else 0,
        "invalid_ohlc_count": res.validation["invalid_ohlc_count"] if res.validation else 0,
        "spread_status": res.validation.get("spread_status", "unavailable") if res.validation else "unavailable",
        "unexpected_gap_count": res.gaps["unexpected_gap_count"] if res.gaps else 0,
        "weekend_gap_count": res.gaps["weekend_gap_count"] if res.gaps else 0,
        "daily_rollover_gap_count": res.gaps["daily_rollover_gap_count"] if res.gaps else 0,
        "max_gap_hours": res.gaps["max_gap_hours"] if res.gaps else 0.0,
        "timezone": "UTC",
        "schema": ["ts", "open", "high", "low", "close", "tick_volume", "spread"],
        "status": status,
        "expected_bars_per_year_magnitude": expected_bars_per_year(tf),
        "errors": res.errors,
    }


def _cal_entry(res) -> dict:
    status = res.status
    if status == "AVAILABLE" and res.validation and res.validation.get("ok"):
        status = "VALIDATED"
    return {
        "dataset": "economic_calendar", "source_file": res.source_file,
        "source_sha256": res.source_sha256,
        "row_count": res.row_count,
        "schema": CALENDAR_COLUMNS,
        "missingness": res.validation["missingness"] if res.validation else {},
        "duplicate_count": res.validation["duplicate_count"] if res.validation else 0,
        "timezone": "UTC",
        "status": status,
        "errors": res.errors,
    }


def build_manifest(out_path: Path | None = None) -> dict:
    m5 = load_m5(); m15 = load_m15(); h1 = load_h1(); h4 = load_h4(); cal = load_calendar()
    manifest = {
        "manifest_version": "v38.2_data_manifest_1",
        "datasets": {
            "XAUUSD_M5": _bar_entry("M5", m5),
            "XAUUSD_M15": _bar_entry("M15", m15),
            "XAUUSD_H1": _bar_entry("H1", h1),
            "XAUUSD_H4": _bar_entry("H4", h4),
            "ECONOMIC_CALENDAR": _cal_entry(cal),
        },
    }
    # H1 overlap note (redundant subset)
    if h1.merge:
        manifest["H1_overlap_note"] = {
            "redundant_file": "XAUUSDm_H1_202401012300_202603032000.csv",
            "overlap_timestamps": h1.merge.get("overlap_timestamps", 0),
            "identical_overlaps": h1.merge.get("identical_overlaps", 0),
            "conflicting_overlaps": h1.merge.get("conflicting_overlaps", 0),
            "note": "2024 file is a 100% redundant subset of the 8y file; not counted as new data.",
        }
    out = Path(out_path) if out_path else (V38_2_DIR / "v38_2_data_manifest.json")
    out.write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


if __name__ == "__main__":
    m = build_manifest()
    print(json.dumps({k: v.get("status") if isinstance(v, dict) else v
                      for k, v in m["datasets"].items()}, indent=2))
