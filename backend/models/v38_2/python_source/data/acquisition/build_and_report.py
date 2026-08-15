"""Build M5/M15 from acquired M1 + produce all V38.2 intraday deliverables.

Reads every downloaded .bi5 hour file under data/raw/dukascopy/xauusd/m1/,
parses to M1, validates, classifies gaps, deterministically aggregates to
M5/M15, validates those, runs cross-feed comparison, and writes:

  data/processed/dukascopy/XAUUSD_M1.csv  (full genuine M1)
  data/processed/dukascopy/XAUUSD_M5.csv
  data/processed/dukascopy/XAUUSD_M15.csv
  v38/v38_2/v38_2_intraday_manifest.json
  v38/v38_2/V38_2_INTRADAY_DATA_REPORT.md

M5/M15 are copied to the gate's expected filenames (data/XAUUSDm_M5.csv,
XAUUSDm_M15.csv) ONLY if they pass validation. The readiness gate is then run
UNMODIFIED. No fabrication, no interpolation, no resample-down.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import bi5_parser, aggregator, cross_feed, dukascopy
from .m1_validation import classify_gaps
from ..loader import load_h1, load_h4
from ..validator import validate_bars
from ..readiness_gate import evaluate as eval_readiness, write_certificate

BACKEND = Path(__file__).resolve().parents[4]
DATA = BACKEND / "data"
RAW_M1 = dukascopy.RAW_ROOT
PROC = DATA / "processed" / "dukascopy"
ACQ_DIR = Path(__file__).resolve().parent
V38_2_DIR = Path(__file__).resolve().parents[2]

TARGET_M5 = DATA / "XAUUSDm_M5.csv"
TARGET_M15 = DATA / "XAUUSDm_M15.csv"


def _iter_bi5_files():
    """Yield (hour_datetime, path) for every .bi5 file under RAW_M1."""
    for p in sorted(RAW_M1.rglob("*h_ticks.bi5")):
        # path: .../m1/{Y}/{M0}/{D}/{HH}h_ticks.bi5
        try:
            parts = p.parts
            hh = int(parts[-1].split("h_")[0])
            dd = int(parts[-2]); mm0 = int(parts[-3]); yy = int(parts[-4])
            hour = datetime(yy, mm0 + 1, dd, hh, tzinfo=timezone.utc)
        except Exception:
            continue
        yield hour, p


def build_m1() -> pd.DataFrame:
    """Parse all acquired .bi5 files into one genuine M1 DataFrame."""
    frames = []
    n_files = 0
    for hour, p in _iter_bi5_files():
        m1 = bi5_parser.parse_hour_to_m1(p, hour)
        if not m1.empty:
            frames.append(m1)
            n_files += 1
    if not frames:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close",
                                     "tick_volume", "spread"])
    m1 = pd.concat(frames, ignore_index=True)
    # drop duplicate timestamps (a tick straddling a minute boundary could in
    # principle double-count; keep first). No fabrication.
    m1 = m1.drop_duplicates("ts", keep="first").sort_values("ts").reset_index(drop=True)
    print(f"[build] parsed {n_files} hour files -> {len(m1)} M1 bars", flush=True)
    return m1


def _day_failure_counts() -> dict:
    """Read per-day failed-hour counts from the acquisition manifest."""
    man_path = ACQ_DIR / "m1_acquisition_manifest.json"
    if not man_path.exists():
        return {}
    try:
        man = json.loads(man_path.read_text())
    except Exception:
        return {}
    return {d: v.get("hours_failed", 0) for d, v in man.get("days", {}).items()}


def run() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)
    retrieval_time = datetime.now(timezone.utc).isoformat()

    m1 = build_m1()
    m1_val = validate_bars(m1)
    m1_gaps = classify_gaps(m1, "M1", _day_failure_counts()) if not m1.empty else {}

    m5 = aggregator.aggregate(m1, "M5")
    m15 = aggregator.aggregate(m1, "M15")
    m5_val = validate_bars(m5)
    m15_val = validate_bars(m15)
    m5_gaps = classify_gaps(m5, "M5", _day_failure_counts()) if not m5.empty else {}
    m15_gaps = classify_gaps(m15, "M15", _day_failure_counts()) if not m15.empty else {}

    # write processed genuine files
    m1.to_csv(PROC / "XAUUSD_M1.csv", index=False)
    m5.to_csv(PROC / "XAUUSD_M5.csv", index=False)
    m15.to_csv(PROC / "XAUUSD_M15.csv", index=False)

    # copy to gate's expected filenames ONLY if validated AND substantively
    # complete (not weakened). A sparse span that merely crosses 365 days is
    # NOT market-ready: require real continuous coverage — enough bars and no
    # multi-week chasm of MISSING data. The 72h threshold applies to UNEXPECTED
    # gaps (potential missing data) only; expected market closures (weekend,
    # holiday) are exempt because the exchange was genuinely closed, not the
    # feed missing data. The threshold value (72h) is NOT weakened.
    MIN_M5_BARS_FOR_GATE = 50_000
    MAX_UNEXPECTED_GAP_HOURS_FOR_GATE = 72  # no unexpected gap longer than a long weekend
    m5_max_unexp = (m5_gaps or {}).get("max_unexpected_gap_hours", 0)
    substantive = (len(m5) >= MIN_M5_BARS_FOR_GATE
                  and m5_max_unexp <= MAX_UNEXPECTED_GAP_HOURS_FOR_GATE)
    m5_ok = m5_val.ok and len(m5) > 0 and substantive
    m15_ok = m15_val.ok and len(m15) > 0 and substantive
    if m5_ok:
        m5.to_csv(TARGET_M5, index=False)
    if m15_ok:
        m15.to_csv(TARGET_M15, index=False)

    # cross-feed comparison vs broker H1 (no merge)
    cross = {}
    if not m1.empty:
        h1d = aggregator.aggregate(m1, "H1")
        h4d = aggregator.aggregate(m1, "H4")
        try:
            cross["H1"] = cross_feed.compare(load_h1().df, h1d, "H1").to_dict()
        except Exception as e:
            cross["H1"] = {"error": str(e)}
        try:
            cross["H4"] = cross_feed.compare(load_h4().df, h4d, "H4").to_dict()
        except Exception as e:
            cross["H4"] = {"error": str(e)}
        h1d.to_csv(PROC / "XAUUSD_H1.csv", index=False)
        h4d.to_csv(PROC / "XAUUSD_H4.csv", index=False)

    # readiness gate (UNMODIFIED)
    gate = eval_readiness()
    cert = write_certificate()

    coverage = {}
    if not m1.empty:
        coverage = {"m1_first": str(m1["ts"].min()), "m1_last": str(m1["ts"].max()),
                    "m1_bars": len(m1), "m5_bars": len(m5), "m15_bars": len(m15)}
        if m5_ok:
            coverage["m5_first"] = str(m5["ts"].min())
            coverage["m5_last"] = str(m5["ts"].max())
        if m15_ok:
            coverage["m15_first"] = str(m15["ts"].min())
            coverage["m15_last"] = str(m15["ts"].max())

    manifest = {
        "source_provider": "Dukascopy", "instrument": "XAUUSD",
        "source_timeframe": "M1 (ticks)", "aggregation_method": "deterministic_OHLC",
        "retrieval_time_utc": retrieval_time,
        "coverage": coverage,
        "m1_validation": {**m1_val.to_dict(), "gaps": m1_gaps},
        "m5_validation": {**m5_val.to_dict(), "gaps": m5_gaps},
        "m15_validation": {**m15_val.to_dict(), "gaps": m15_gaps},
        "cross_feed": cross,
        "m5_copied_to_gate": m5_ok, "m15_copied_to_gate": m15_ok,
        "readiness_gate": gate.to_dict(),
        "spread_status_m5": m5_val.spread_status,
        "spread_status_m15": m15_val.spread_status,
        "note": "genuine Dukascopy data; no fabrication/interpolation/duplication",
    }
    (V38_2_DIR / "v38_2_intraday_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str))

    _write_report(manifest)
    print(f"[build] DONE — M1={len(m1)} M5={len(m5)} M15={len(m15)} "
          f"gate={gate.status}", flush=True)
    return manifest


def _write_report(manifest: dict) -> None:
    cov = manifest["coverage"]
    m1v = manifest["m1_validation"]; m5v = manifest["m5_validation"]; m15v = manifest["m15_validation"]
    g = manifest["readiness_gate"]
    cross = manifest["cross_feed"]

    def _gap_line(gaps, label):
        if not gaps:
            return f"- {label}: n/a (no data)\n"
        return (f"- {label}: expected={gaps.get('expected_gap_count',0)} "
                f"market_closed={gaps.get('market_closed_count',0)} "
                f"unexpected={gaps.get('unexpected_gap_count',0)} "
                f"source_outage={gaps.get('source_outage_count',0)} "
                f"max_gap_h={gaps.get('max_gap_hours',0)}\n")

    lines = []
    lines.append("# V38.2 Intraday Data Report (M1 → M5/M15)\n")
    lines.append(f"Retrieved: {manifest['retrieval_time_utc']}\n")
    lines.append(f"Source: {manifest['source_provider']} XAUUSD M1 ticks (.bi5 LZMA)\n")
    lines.append("Aggregation: deterministic OHLC (open=first, high=max, low=min, "
                 "close=last, tick_volume=sum, spread=mean observed). No fabrication, "
                 "no interpolation, no resample-down.\n\n")

    lines.append("## Coverage\n")
    if cov:
        lines.append(f"- M1: {cov.get('m1_bars',0)} bars, {cov.get('m1_first','?')} → {cov.get('m1_last','?')}\n")
        lines.append(f"- M5: {cov.get('m5_bars',0)} bars\n")
        lines.append(f"- M15: {cov.get('m15_bars',0)} bars\n")
        if cov.get("m5_first"):
            lines.append(f"- M5 span: {cov.get('m5_first')} → {cov.get('m5_last')}\n")
        if cov.get("m15_first"):
            lines.append(f"- M15 span: {cov.get('m15_first')} → {cov.get('m15_last')}\n")
    else:
        lines.append("- No M1 data acquired yet.\n")
    lines.append("\n## Validation (Phase E criteria)\n")
    lines.append(f"- M1: ok={m1v.get('ok')} nan={m1v.get('nan_count',0)} inf={m1v.get('inf_count',0)} "
                 f"invalid_ohlc={m1v.get('invalid_ohlc_count',0)} dup_ts={m1v.get('duplicate_ts_count',0)} "
                 f"spread={m1v.get('spread_status')}\n")
    lines.append(f"- M5: ok={m5v.get('ok')} nan={m5v.get('nan_count',0)} inf={m5v.get('inf_count',0)} "
                 f"invalid_ohlc={m5v.get('invalid_ohlc_count',0)} dup_ts={m5v.get('duplicate_ts_count',0)} "
                 f"spread={m5v.get('spread_status')}\n")
    lines.append(f"- M15: ok={m15v.get('ok')} nan={m15v.get('nan_count',0)} inf={m15v.get('inf_count',0)} "
                 f"invalid_ohlc={m15v.get('invalid_ohlc_count',0)} dup_ts={m15v.get('duplicate_ts_count',0)} "
                 f"spread={m15v.get('spread_status')}\n")
    lines.append("\n## Gap classification (gaps are NOT filled; all classified)\n")
    lines.append(_gap_line(m1v.get("gaps"), "M1"))
    lines.append(_gap_line(m5v.get("gaps"), "M5"))
    lines.append(_gap_line(m15v.get("gaps"), "M15"))

    lines.append("\n## Cross-feed comparison vs broker (no merge)\n")
    for tf, r in cross.items():
        if "error" in r:
            lines.append(f"- {tf}: skipped ({r['error']})\n")
        else:
            lines.append(f"- {tf}: overlap={r.get('overlap_timestamps',0)} "
                         f"mean_close_diff={r.get('mean_close_diff','?')} "
                         f"pct_within_$0.50={r.get('pct_close_within_0_5usd','?')}\n")

    lines.append("\n## Readiness gate (unmodified)\n")
    lines.append(f"- status: **{g['status']}**\n")
    if g.get("blocking_reasons"):
        lines.append("- blocking reasons:\n")
        for r in g["blocking_reasons"]:
            lines.append(f"  - {r}\n")

    lines.append("\n## Honesty note\n")
    lines.append("Coverage reflects exactly what was genuinely downloaded from Dukascopy. "
                 "Weekend/holiday closures produce absent bars (not filled). Failed hours "
                 "(503/timeout) are recorded in m1_acquisition_manifest.json and not "
                 "fabricated. Expected counts are never reported as achieved counts.\n")
    (V38_2_DIR / "V38_2_INTRADAY_DATA_REPORT.md").write_text("".join(lines))


if __name__ == "__main__":
    run()
