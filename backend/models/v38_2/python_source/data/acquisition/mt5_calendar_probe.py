#!/usr/bin/env python3
"""V38.2 — FBS MT5 Economic Calendar export & PIT capability probe (Windows-side).

Runs on the operator's Windows machine with the FBS MT5 terminal. Probes whether
the MT5 economic calendar can provide HISTORICAL POINT-IN-TIME forecast values.

CRITICAL DISTINCTION:
  A "Forecast" column visible in the MT5 calendar UI does NOT prove PIT. The
  value displayed today may be a CURRENT-REVISED forecast (the consensus as of
  today's data revision), NOT the consensus that was actually known immediately
  before the historical release. Using a current-revised forecast as a PIT
  forecast creates look-ahead leakage.

This script:
  1. Exports MT5 calendar events (USD, 2018→2026) to a raw CSV.
  2. Maps to the V38.2 schema (ts, country, currency, event_name, category,
     importance, actual, forecast, previous, revised_previous, unit,
     directionality, release_ts).
  3. Runs the existing V38.2 PIT leakage test (calendar.pit_leakage_test).
  4. Reports an explicit verdict: PIT_VERIFIED / PIT_UNVERIFIED / PIT_BLOCKED /
     SOURCE_UNAVAILABLE.

NON-NEGOTIABLE:
  - Does NOT manufacture a calendar file.
  - Does NOT create backend/data/economic_calendar.csv unless PIT is verified.
  - Does NOT remove, weaken, or substitute the locked Option-B features.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import MetaTrader5 as mt5
    import pandas as pd
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    pd = None

# Add backend to path so we can import the V38.2 PIT validator
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "mt5_raw"

V38_SCHEMA = ["ts", "country", "currency", "event_name", "category",
              "importance", "actual", "forecast", "previous", "revised_previous",
              "unit", "directionality", "release_ts"]

IMPORTANCE_MAP = {0: "none", 1: "low", 2: "medium", 3: "high"}


def _probe_calendar_capabilities() -> dict:
    """Probe what the MT5 calendar API exposes."""
    caps = {
        "mt5_available": MT5_AVAILABLE,
        "calendar_history_available": False,
        "forecast_column_exists": False,
        "previous_column_exists": False,
        "revised_previous_column_exists": False,
        "release_ts_column_exists": False,
        "importance_available": False,
        "usd_events_found": False,
        "coverage_2018_to_2026": False,
        "historical_vintages": False,
    }
    if not MT5_AVAILABLE:
        return caps
    try:
        # Check if calendar_history() exists (MetaTrader5 >= 5.0.45)
        caps["calendar_history_available"] = hasattr(mt5, "calendar_history")
        caps["calendar_value_history_by_id"] = hasattr(mt5, "calendar_value_history_by_id")
    except Exception:
        pass
    return caps


def _map_calendar_rows(values) -> "pd.DataFrame":
    """Map MT5 calendar value records to V38.2 schema."""
    if values is None or len(values) == 0:
        return pd.DataFrame(columns=V38_SCHEMA)
    df = pd.DataFrame(values)
    mapped = pd.DataFrame()
    if "time" in df.columns:
        mapped["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    if "country" in df.columns:
        mapped["country"] = df["country"]
    if "currency" not in df.columns and "country" in df.columns:
        # Derive currency from country code if needed
        cur_map = {"US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY",
                   "CH": "CHF", "AU": "AUD", "CA": "CAD", "NZ": "NZD"}
        mapped["currency"] = df["country"].map(cur_map)
    else:
        mapped["currency"] = df.get("currency")
    if "event_name" in df.columns:
        mapped["event_name"] = df["event_name"]
    elif "name" in df.columns:
        mapped["event_name"] = df["name"]
    mapped["category"] = df.get("section", df.get("category"))
    if "importance" in df.columns:
        mapped["importance"] = df["importance"].map(IMPORTANCE_MAP).fillna("none")
        # Also keep numeric for reference
    else:
        mapped["importance"] = "none"
    # Core values: actual, forecast, previous
    for col in ("actual", "forecast", "previous"):
        if col in df.columns:
            mapped[col] = df[col]
        else:
            mapped[col] = None
    # revised_previous — MT5 does NOT typically expose this
    if "revised" in df.columns:
        mapped["revised_previous"] = df["revised"]
    else:
        mapped["revised_previous"] = None
    mapped["unit"] = df.get("unit", None)
    # directionality — not standard in MT5
    mapped["directionality"] = None
    # release_ts — THE CRITICAL PIT ANCHOR
    # MT5 calendar records have the event time as "time". There is typically NO
    # separate "release_ts" or "last_update" / "revision_ts" column. This is the
    # key limitation: without a revision timestamp, PIT cannot be proven.
    if "release_ts" in df.columns:
        mapped["release_ts"] = pd.to_datetime(df["release_ts"], unit="s", utc=True)
    elif "last_update" in df.columns:
        mapped["release_ts"] = pd.to_datetime(df["last_update"], unit="s", utc=True)
    else:
        mapped["release_ts"] = None
    return mapped


def export_and_audit(start: str, end: str, out_dir: Path,
                     countries: str = "US") -> dict:
    """Export MT5 calendar and run PIT test."""
    out_dir.mkdir(parents=True, exist_ok=True)
    caps = _probe_calendar_capabilities()

    if not MT5_AVAILABLE:
        return _blocked(out_dir, start, end, caps)

    if not mt5.initialize():
        return _blocked(out_dir, start, end, caps,
                        reason="mt5.initialize() failed")

    caps["calendar_history_available"] = hasattr(mt5, "calendar_history")

    raw_path = out_dir / "mt5_calendar_raw.csv"

    # Try calendar_history (historical events)
    values = None
    if hasattr(mt5, "calendar_history"):
        try:
            from datetime import datetime as dt
            sd = dt.fromisoformat(start)
            ed = dt.fromisoformat(end)
            values = mt5.calendar_history(sd, ed)
        except Exception as e:
            caps["calendar_history_error"] = str(e)

    # Also try calendar_value_history_by_id for revision vintages
    caps["historical_vintages"] = hasattr(mt5, "calendar_value_history_by_id")
    if hasattr(mt5, "calendar_value_history_by_id") and values is not None and len(values) > 0:
        # Test: does calendar_value_history_by_id return multiple vintages?
        sample_id = values[0].get("event_id") if hasattr(values[0], "get") else getattr(values[0], "event_id", None)
        if sample_id:
            try:
                vhist = mt5.calendar_value_history_by_id(sample_id)
                caps["vintages_returned_for_sample"] = len(vhist) if vhist else 0
                if vhist and len(vhist) > 1:
                    caps["historical_vintages"] = True
            except Exception as e:
                caps["vintage_probe_error"] = str(e)

    mt5.shutdown()

    if values is None or len(values) == 0:
        caps["calendar_data_returned"] = False
        result = _blocked(out_dir, start, end, caps,
                          reason="MT5 calendar_history returned no data")
        return result

    caps["calendar_data_returned"] = True
    df = _map_calendar_rows(values)

    # Filter to requested countries
    if countries and "country" in df.columns:
        ctry_list = countries.split(",")
        df = df[df["country"].isin(ctry_list)].reset_index(drop=True)

    # Write raw export (NOT to economic_calendar.csv)
    df.to_csv(raw_path, index=False)
    caps["raw_rows"] = int(len(df))

    # Check column availability
    caps["forecast_column_exists"] = "forecast" in df.columns
    caps["previous_column_exists"] = "previous" in df.columns
    caps["revised_previous_column_exists"] = "revised_previous" in df.columns and df["revised_previous"].notna().any()
    caps["release_ts_column_exists"] = "release_ts" in df.columns and df["release_ts"].notna().any()
    caps["importance_available"] = "importance" in df.columns
    caps["usd_events_found"] = "currency" in df.columns and (df["currency"] == "USD").any()

    # Coverage check
    if "ts" in df.columns and len(df):
        caps["earliest_event"] = str(df["ts"].min())
        caps["latest_event"] = str(df["ts"].max())
        caps["coverage_2018_to_2026"] = (
            df["ts"].min().year <= 2018 and df["ts"].max().year >= 2025)

    # Run the V38.2 PIT leakage test
    pit_verdict = _run_pit_test(df)
    caps["pit_verdict"] = pit_verdict["pit_status"].upper()

    result = {
        "status": "COMPLETED" if len(df) > 0 else "NO_DATA",
        "capabilities": caps,
        "pit_test": pit_verdict,
        "raw_export": str(raw_path),
        "economic_calendar_csv_written": False,
        "note": "economic_calendar.csv NOT written — PIT must be verified first. "
                "A current-revised forecast is NOT a PIT forecast.",
    }
    (out_dir / "mt5_calendar_audit.json").write_text(
        json.dumps(result, indent=2, default=str))
    return result


def _run_pit_test(df: "pd.DataFrame") -> dict:
    """Run the existing V38.2 PIT leakage test."""
    try:
        from v38.v38_2.data.acquisition.calendar import pit_leakage_test
        from v38.v38_2.data.acquisition.te_pit_adapter import pit_validation_report
        base = pit_leakage_test(df)
        full = pit_validation_report(df)
        return {
            "pit_status": base["pit_status"],
            "checks": base["checks"],
            "leakage_findings": base["leakage_findings"],
            "may_ingest": full["may_ingest"],
            "note": full["note"],
        }
    except Exception as e:
        return {
            "pit_status": "unverified",
            "error": str(e),
            "leakage_findings": ["PIT test could not be executed"],
            "may_ingest": False,
        }


def _blocked(out_dir: Path, start: str, end: str, caps: dict,
             reason: str = "MetaTrader5 package not importable — Linux environment") -> dict:
    """Return a SOURCE_UNAVAILABLE / BLOCKED result (no fabrication)."""
    caps["mt5_available"] = MT5_AVAILABLE
    result = {
        "status": "SOURCE_UNAVAILABLE" if not MT5_AVAILABLE else "BLOCKED_BY_ENVIRONMENT",
        "reason": reason,
        "capabilities": caps,
        "pit_test": {
            "pit_status": "blocked",
            "leakage_findings": ["MT5 calendar source not accessible — cannot test PIT"],
            "may_ingest": False,
        },
        "raw_export": None,
        "economic_calendar_csv_written": False,
        "note": "No calendar file manufactured. Option-B features remain PIT_BLOCKED_NO_SOURCE.",
    }
    (out_dir / "mt5_calendar_audit.json").write_text(
        json.dumps(result, indent=2, default=str))
    return result


def main():
    ap = argparse.ArgumentParser(description="FBS MT5 economic calendar PIT probe")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default="2026-03-04")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--countries", default="US")
    args = ap.parse_args()
    result = export_and_audit(args.start, args.end, Path(args.out_dir),
                              countries=args.countries)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
