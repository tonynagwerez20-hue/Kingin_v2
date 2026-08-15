#!/usr/bin/env python3
"""V38.2 — FBS MT5 M1 history acquisition & audit (Windows-side tool).

This script runs on the OPERATOR'S Windows machine where the FBS MT5 terminal
is installed. It cannot run on the Linux development container (the official
MetaTrader5 Python package is a Windows-only native extension).

Purpose:
  - Retrieve genuine XAUUSDm M1 history from the FBS MT5 terminal.
  - Year-by-year chunked retrieval with resumability + duplicate protection.
  - UTC normalization, deterministic CSV output, SHA-256 provenance, manifest.
  - Measure and report earliest/latest, bars/year, gaps, duplicates, NaN/inf,
    invalid OHLC, spread availability, timezone.
  - Export to a TEMPORARY raw location — NEVER to backend/data/XAUUSDm_M5.csv
    or backend/data/XAUUSDm_M15.csv until the V38.2 pipeline validates it.

Usage (Windows, Python 3.8-3.11, MetaTrader5 installed, FBS terminal running):
    python mt5_m1_acquirer.py --symbol XAUUSDm --start 2018-01-01 --end 2026-03-04
    python mt5_m1_acquirer.py --symbol XAUUSDm --start 2018-01-01 --end 2026-03-04 --resume

Output:
    <out_dir>/XAUUSDm_M1_raw.csv          — deterministic M1 CSV (UTC)
    <out_dir>/XAUUSDm_M1_manifest.json    — per-year manifest with SHA-256
    <out_dir>/XAUUSDm_M1_audit.json       — measured metrics

NON-NEGOTIABLE:
  - No fabrication, interpolation, or synthetic bars.
  - No H1→M1 resampling.
  - Reports exactly what MT5 returns; missing ranges are reported, NOT filled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import MetaTrader5 as mt5
    import pandas as pd
    import numpy as np
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    pd = None
    np = None

DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "mt5_raw"

REQUIRED_COLS = ["ts", "open", "high", "low", "close", "tick_volume", "spread"]


def _utc(ts_mt5: int) -> datetime:
    """MT5 returns timestamps as seconds since epoch (broker-local, but the
    integer is epoch-UTC). Convert to timezone-aware UTC."""
    return datetime.fromtimestamp(ts_mt5, tz=timezone.utc)


def _year_ranges(start: str, end: str):
    """Yield (year, start_dt, end_dt) tuples for each year in [start, end]."""
    sy = int(start[:4]); ey = int(end[:4])
    for y in range(sy, ey + 1):
        ys = datetime(y, 1, 1, tzinfo=timezone.utc)
        ye = datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        if y == sy:
            ys = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        if y == ey:
            ye = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
        yield y, ys, ye


def _df_from_rates(rates) -> "pd.DataFrame":
    """Convert MT5 copy_rates result to a normalized DataFrame."""
    df = pd.DataFrame(rates)
    if len(df) == 0:
        return df
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.rename(columns={
        "tick_volume": "tick_volume",
        "real_volume": "real_volume",
    })
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    df["tick_volume"] = df["tick_volume"].astype(int)
    if "spread" in df.columns:
        df["spread"] = df["spread"].astype(int)
    else:
        df["spread"] = np.nan
    if "real_volume" in df.columns:
        df["real_volume"] = df["real_volume"].astype(float)
    else:
        df["real_volume"] = np.nan
    return df[["ts", "open", "high", "low", "close", "tick_volume", "spread",
               "real_volume"]].sort_values("ts").reset_index(drop=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_year_df(df: "pd.DataFrame") -> dict:
    """Compute validation metrics for a year's M1 DataFrame."""
    if len(df) == 0:
        return {"bar_count": 0, "first": None, "last": None, "unique_ts": 0,
                "duplicate_count": 0, "nan_count": 0, "inf_count": 0,
                "invalid_ohlc_count": 0, "largest_gap_h": 0,
                "trading_days": 0}
    dups = int(df["ts"].duplicated().sum())
    nan = int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    inf = int(np.isinf(df[["open", "high", "low", "close"]]).any(axis=1).sum())
    invalid_ohlc = int(((df["high"] < df["low"]) |
                        (df["high"] < df["open"]) |
                        (df["high"] < df["close"]) |
                        (df["low"] > df["open"]) |
                        (df["low"] > df["close"])).sum())
    gaps = df["ts"].diff().dropna()
    max_gap_h = round(gaps.max().total_seconds() / 3600, 2) if len(gaps) else 0
    return {
        "bar_count": int(len(df)),
        "first": df["ts"].min().isoformat(),
        "last": df["ts"].max().isoformat(),
        "unique_ts": int(df["ts"].nunique()),
        "duplicate_count": dups,
        "nan_count": nan,
        "inf_count": inf,
        "invalid_ohlc_count": invalid_ohlc,
        "largest_gap_h": max_gap_h,
        "trading_days": int(df["ts"].dt.date.nunique()),
    }


def acquire(symbol: str, start: str, end: str, out_dir: Path,
            resume: bool = False) -> dict:
    """Main acquisition: year-by-year retrieval with resumability."""
    if not MT5_AVAILABLE:
        return _blocked(out_dir, symbol, start, end)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "XAUUSDm_M1_manifest.json"
    csv_path = out_dir / "XAUUSDm_M1_raw.csv"

    # Initialize MT5
    if not mt5.initialize():
        return _blocked(out_dir, symbol, start, end,
                        reason="mt5.initialize() failed — terminal not running")

    # Terminal/account info
    term = mt5.terminal_info()
    acct = mt5.account_info()
    term_info = {}
    if term:
        term_info = {
            "name": term.name, "path": term.path,
            "data_path": term.data_path, "timezone": term.timezone,
            "trade_allowed": term.trade_allowed,
        }
    acct_info = {}
    if acct:
        acct_info = {"login": acct.login, "server": acct.server,
                     "currency": acct.currency, "leverage": acct.leverage}

    # Symbol check
    sym_info = mt5.symbol_info(symbol)
    if sym_info is None:
        return _blocked(out_dir, symbol, start, end,
                        reason=f"symbol {symbol} not found")
    sym_props = {"name": sym_info.name, "visible": sym_info.visible,
                 "digits": sym_info.digits, "trade_mode": sym_info.trade_mode}

    # Resumability
    manifest = {"symbol": symbol, "start": start, "end": end,
                "terminal": term_info, "account": acct_info,
                "symbol_info": sym_props, "years": {}}
    if resume and manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        manifest["years"] = old.get("years", {})

    all_dfs = []
    for year, ys, ye in _year_ranges(start, end):
        ykey = str(year)
        if resume and ykey in manifest["years"] and manifest["years"][ykey].get("sha256"):
            # Already acquired this year — load from CSV chunk
            chunk_path = out_dir / f"XAUUSDm_M1_{year}.csv"
            if chunk_path.exists():
                all_dfs.append(pd.read_csv(chunk_path, parse_dates=["ts"]))
                continue
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, ys, ye)
        if rates is None or len(rates) == 0:
            manifest["years"][ykey] = {"bar_count": 0, "first": None, "last": None,
                                       "error": "no data returned"}
            continue
        df = _df_from_rates(rates)
        # Duplicate protection: deduplicate on ts, keep last
        df = df.drop_duplicates(subset=["ts"], keep="last").reset_index(drop=True)
        chunk_path = out_dir / f"XAUUSDm_M1_{year}.csv"
        df.to_csv(chunk_path, index=False)
        sha = _sha256_file(chunk_path)
        metrics = _validate_year_df(df)
        metrics["sha256"] = sha
        manifest["years"][ykey] = metrics
        all_dfs.append(df)

    mt5.shutdown()

    # Combine
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["ts"], keep="last")
        combined = combined.sort_values("ts").reset_index(drop=True)
        combined.to_csv(csv_path, index=False)
        overall = _validate_year_df(combined)
        overall["sha256"] = _sha256_file(csv_path)
    else:
        combined = pd.DataFrame()
        overall = _validate_year_df(combined)

    manifest["overall"] = overall
    manifest["acquired_utc"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    # Audit report
    audit = _build_audit(manifest, combined, term_info)
    (out_dir / "XAUUSDm_M1_audit.json").write_text(
        json.dumps(audit, indent=2, default=str))
    return audit


def _blocked(out_dir: Path, symbol: str, start: str, end: str,
             reason: str = "MetaTrader5 package not importable — Linux environment") -> dict:
    """Return a BLOCKED_BY_ENVIRONMENT result (no fabrication)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = {
        "status": "BLOCKED_BY_ENVIRONMENT",
        "reason": reason,
        "symbol": symbol, "start": start, "end": end,
        "earliest_available": None, "latest_available": None,
        "total_m1_bars": 0, "bars_per_year": {}, "trading_days": 0,
        "missing_dates": "UNKNOWN", "max_gap_h": None, "unexpected_gaps": "UNKNOWN",
        "duplicates": 0, "nan_count": 0, "inf_count": 0, "invalid_ohlc_count": 0,
        "spread_available": "UNKNOWN", "timezone": "UNKNOWN",
        "note": "This script must be run on Windows with the FBS MT5 terminal. "
                "No data fabricated. No assumptions made about MT5 coverage.",
    }
    (out_dir / "XAUUSDm_M1_audit.json").write_text(
        json.dumps(audit, indent=2, default=str))
    return audit


def _build_audit(manifest: dict, df: "pd.DataFrame", term_info: dict) -> dict:
    overall = manifest["overall"]
    tz_offset = term_info.get("timezone", "unknown")
    bars_per_year = {y: m.get("bar_count", 0) for y, m in manifest["years"].items()}
    return {
        "status": "COMPLETED",
        "symbol": manifest["symbol"],
        "earliest_available": overall["first"],
        "latest_available": overall["last"],
        "total_m1_bars": overall["bar_count"],
        "total_unique_m1_bars": overall["unique_ts"],
        "bars_per_year": bars_per_year,
        "trading_days": overall["trading_days"],
        "missing_dates": "see gap analysis",
        "max_gap_h": overall["largest_gap_h"],
        "unexpected_gaps": "see gap_analysis.py",
        "duplicates": overall["duplicate_count"],
        "nan_count": overall["nan_count"],
        "inf_count": overall["inf_count"],
        "invalid_ohlc_count": overall["invalid_ohlc_count"],
        "spread_available": "yes" if "spread" in df.columns and df["spread"].notna().any() else "no",
        "real_volume_available": "yes" if "real_volume" in df.columns and df["real_volume"].notna().any() else "no",
        "timezone": tz_offset,
        "utc_normalization": "MT5 epoch seconds → UTC (broker offset documented in terminal.timezone)",
        "sha256": overall.get("sha256"),
        "sha256_per_year": {y: m.get("sha256") for y, m in manifest["years"].items()},
    }


def main():
    ap = argparse.ArgumentParser(description="FBS MT5 M1 acquisition (Windows-side)")
    ap.add_argument("--symbol", default="XAUUSDm")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default="2026-03-04")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    result = acquire(args.symbol, args.start, args.end,
                     Path(args.out_dir), resume=args.resume)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
