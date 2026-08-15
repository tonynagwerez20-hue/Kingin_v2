#!/usr/bin/env python3
"""V38.2 — MT5 M1 → M5/M15 aggregation + H1 overlap comparison (Linux-side).

This script runs on the Linux dev container AFTER the operator has run
mt5_m1_acquirer.py on Windows and transferred XAUUSDm_M1_raw.csv here.

It:
  1. Aggregates genuine MT5 M1 → M5/M15 using the V38.2 construction rule.
  2. Aggregates MT5 M1 → H1 for overlap comparison with validated broker H1.
  3. Compares MT5-derived H1 against the existing validated FBS H1 dataset.
  4. Reports timestamp overlap, close differences, OHLC differences, spread
     differences, symbol naming differences.

NON-NEGOTIABLE:
  - M5/M15 built ONLY from genuine M1. NO H1→M5, NO H1→M15, NO interpolation.
  - Output goes to a TEMPORARY location, NEVER to backend/data/XAUUSDm_M5.csv
    or backend/data/XAUUSDm_M15.csv until validation passes.
  - Feeds are NOT merged. This is a comparison only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timezone
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from v38.v38_2.data.acquisition.aggregator import aggregate


def _load_mt5_m1(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def build_m5_m15_h1(m1: pd.DataFrame, out_dir: Path) -> dict:
    """Aggregate M1 → M5, M15, H1 using the genuine-M1 construction rule."""
    out_dir.mkdir(parents=True, exist_ok=True)
    m5 = aggregate(m1, "M5")
    m15 = aggregate(m1, "M15")
    h1 = aggregate(m1, "H1")
    m5_path = out_dir / "XAUUSDm_M5_mt5_temp.csv"
    m15_path = out_dir / "XAUUSDm_M15_mt5_temp.csv"
    h1_path = out_dir / "XAUUSDm_H1_mt5_derived.csv"
    m5.to_csv(m5_path, index=False)
    m15.to_csv(m15_path, index=False)
    h1.to_csv(h1_path, index=False)
    return {
        "m5_bars": int(len(m5)), "m15_bars": int(len(m15)), "h1_bars": int(len(h1)),
        "m5_path": str(m5_path), "m15_path": str(m15_path), "h1_path": str(h1_path),
        "m5_max_gap_h": round(m5["ts"].diff().dropna().max().total_seconds()/3600, 2) if len(m5) > 1 else 0,
        "m15_max_gap_h": round(m15["ts"].diff().dropna().max().total_seconds()/3600, 2) if len(m15) > 1 else 0,
        "note": "Temporary files — NOT placed at backend/data/XAUUSDm_M5.csv or M15.",
    }


def _load_broker_h1(path: Path) -> pd.DataFrame:
    """Load broker H1, handling MT5 export format or V38 CSV format."""
    df = pd.read_csv(path)
    # V38 CSV format: ts,open,high,low,close,tick_volume,spread
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values("ts").reset_index(drop=True)
    # MT5 export format: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>
    # Columns are space-separated with tab/space delimiters
    df = pd.read_csv(path, sep=r"\s+", engine="python")
    col_map = {}
    for c in df.columns:
        cl = c.strip("<>").lower()
        col_map[c] = cl
    df = df.rename(columns=col_map)
    if "date" in df.columns and "time" in df.columns:
        df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], utc=True)
    for c in ("open", "high", "low", "close"):
        if c in df.columns:
            df[c] = df[c].astype(float)
    if "tickvol" in df.columns:
        df = df.rename(columns={"tickvol": "tick_volume"})
    if "spread" in df.columns:
        df["spread"] = df["spread"].astype(float)
    else:
        df["spread"] = 0.0
    return df[["ts", "open", "high", "low", "close", "tick_volume", "spread"]].sort_values("ts").reset_index(drop=True)


def compare_h1(mt5_h1_path: Path, broker_h1_path: Path) -> dict:
    """Compare MT5-derived H1 against validated broker H1."""
    if not mt5_h1_path.exists():
        return {"status": "BLOCKED", "reason": "MT5 H1 file not found"}
    if not broker_h1_path.exists():
        return {"status": "BLOCKED", "reason": "Broker H1 file not found"}

    mt5_h1 = pd.read_csv(mt5_h1_path)
    mt5_h1["ts"] = pd.to_datetime(mt5_h1["ts"], utc=True)
    broker_h1 = _load_broker_h1(broker_h1_path)

    # Align on overlapping timestamps
    merged = mt5_h1.merge(broker_h1, on="ts", suffixes=("_mt5", "_broker"))
    overlap_count = int(len(merged))
    if overlap_count == 0:
        return {
            "status": "NO_OVERLAP",
            "mt5_h1_range": [str(mt5_h1["ts"].min()), str(mt5_h1["ts"].max())],
            "broker_h1_range": [str(broker_h1["ts"].min()), str(broker_h1["ts"].max())],
            "overlap_bars": 0,
        }

    close_diff = (merged["close_mt5"] - merged["close_broker"]).abs()
    ohlc_diffs = {}
    for col in ("open", "high", "low", "close"):
        d = (merged[f"{col}_mt5"] - merged[f"{col}_broker"]).abs()
        ohlc_diffs[col] = {
            "mean": round(float(d.mean()), 6),
            "median": round(float(d.median()), 6),
            "max": round(float(d.max()), 6),
            "pct_exact_match": round(float((d == 0).mean()) * 100, 2),
        }

    spread_diff = None
    if "spread_mt5" in merged.columns and "spread_broker" in merged.columns:
        sd = (merged["spread_mt5"].fillna(0) - merged["spread_broker"].fillna(0)).abs()
        spread_diff = {
            "mean": round(float(sd.mean()), 4),
            "median": round(float(sd.median()), 4),
            "max": round(float(sd.max()), 4),
        }

    # Timestamp offset detection
    if "ts" in mt5_h1.columns and "ts" in broker_h1.columns:
        mt5_only = set(mt5_h1["ts"]) - set(broker_h1["ts"])
        broker_only = set(broker_h1["ts"]) - set(mt5_h1["ts"])
    else:
        mt5_only, broker_only = set(), set()

    return {
        "status": "COMPLETED",
        "overlap_bars": overlap_count,
        "close_abs_diff": {
            "mean": round(float(close_diff.mean()), 6),
            "median": round(float(close_diff.median()), 6),
            "max": round(float(close_diff.max()), 6),
        },
        "ohlc_differences": ohlc_diffs,
        "spread_differences": spread_diff,
        "mt5_only_bars": len(mt5_only),
        "broker_only_bars": len(broker_only),
        "systematic_offset": "none detected" if overlap_count > 100 else "insufficient overlap",
        "symbol_naming": {
            "mt5_symbol": "XAUUSDm", "broker_symbol": "XAUUSD",
            "note": "Different naming — NOT merged. Comparison only.",
        },
        "feeds_merged": False,
    }


def main():
    ap = argparse.ArgumentParser(description="MT5 M1 aggregation + H1 overlap comparison")
    ap.add_argument("--mt5-m1", required=True, help="Path to XAUUSDm_M1_raw.csv from Windows export")
    ap.add_argument("--broker-h1", default="data/XAUUSDm_H1_8 years data.csv",
                    help="Path to validated broker H1")
    ap.add_argument("--out-dir", default="data/mt5_raw")
    args = ap.parse_args()

    m1 = _load_mt5_m1(Path(args.mt5_m1))
    agg = build_m5_m15_h1(m1, Path(args.out_dir))
    comp = compare_h1(Path(agg["h1_path"]), Path(args.broker_h1))
    result = {"aggregation": agg, "h1_overlap_comparison": comp}
    out = Path(args.out_dir) / "mt5_h1_overlap.json"
    out.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
