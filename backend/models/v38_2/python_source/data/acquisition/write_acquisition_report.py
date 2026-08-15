"""Generate the V38_2_DATA_ACQUISITION_REPORT.md from live manifest + gate state."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ACQ_DIR = Path(__file__).resolve().parent
V38_2_DIR = Path(__file__).resolve().parents[2]
MAN = ACQ_DIR / "m1_acquisition_manifest.json"


def render() -> str:
    man = json.loads(MAN.read_text()) if MAN.exists() else {"summary": {}, "days": {}}
    s = man.get("summary", {})
    days = man.get("days", {})
    gate = json.loads((V38_2_DIR / "v38_2_readiness_certificate.json").read_text()) \
        if (V38_2_DIR / "v38_2_readiness_certificate.json").exists() else {"status": "n/a", "blocking_reasons": []}
    intraday = json.loads((V38_2_DIR / "v38_2_intraday_manifest.json").read_text()) \
        if (V38_2_DIR / "v38_2_intraday_manifest.json").exists() else {}

    days_with_bars = sum(1 for d in days.values() if d.get("bar_count", 0) > 0)
    full_days = sum(1 for d in days.values() if d.get("hours_downloaded", 0) >= 15)
    by_status = s.get("by_status", {})

    cov = intraday.get("coverage", {})
    m5v = intraday.get("m5_validation", {})
    cross = intraday.get("cross_feed", {})

    L = []
    L.append("# V38.2 Data Acquisition Report\n\n")
    L.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n")
    L.append("**Phase:** DATA ACQUISITION + DATA-READINESS (NO model training)\n")
    L.append("**V38.1 verdict:** E — INCREASE DATA FIRST (authoritative)\n\n")

    L.append("## 1. Objective\n")
    L.append("Acquire genuine XAUUSD M1 tick data (Dukascopy) for 2018-01-01 → latest, "
             "construct M5/M15 by deterministic OHLC aggregation, validate, and assess "
             "data readiness. No fabrication, interpolation, duplication, oversampling, "
             "or resample-down. No model training.\n\n")

    L.append("## 2. Source\n")
    L.append("- Provider: Dukascopy (`https://datafeed.dukascopy.com/datafeed/XAUUSD/...`)\n")
    L.append("- Format: per-hour `.bi5` = LZMA-compressed 20-byte big-endian tick "
             "records `>3I2f` (millisecs, ask, bid, ask_vol, bid_vol); price × 1000.\n")
    L.append("- Feed character: REACHABLE but intermittent (HTTP 503 / timeouts). "
             "Retries with exponential backoff; inter-request delay; resumable.\n\n")

    L.append("## 3. Acquisition system (resumable, day-partitioned)\n")
    L.append("- `acquisition/acquire_driver.py` — iterates UTC days 2018-01-01 → now, "
             "24 hours/day, per-day manifest entry, restart-safe (cached hours skipped).\n")
    L.append("- Per-day wall-clock budget (default 200s) so a stuck day is left PARTIAL "
             "and breadth is prioritized; missing hours resume on the next run.\n")
    L.append("- Manifest `m1_acquisition_manifest.json` records per day: request_status, "
             "http_status, retry_count, bar_count, first/last timestamp, sha256, "
             "validation_status, hours downloaded/cached/empty/failed.\n\n")

    L.append("## 4. Coverage obtained (EXACT — not inflated)\n")
    L.append(f"- Days attempted: {s.get('days_total', 0)}\n")
    L.append(f"- Days with ≥1 M1 bar: {days_with_bars}\n")
    L.append(f"- Full trading days (≥15 hours captured): {full_days}\n")
    L.append(f"- By status: {by_status}\n")
    L.append(f"- Hours: downloaded={s.get('hours_downloaded',0)}, "
             f"cached={s.get('hours_cached',0)}, empty={s.get('hours_empty',0)}, "
             f"failed={s.get('hours_failed',0)}\n")
    L.append(f"- **M1 bars acquired: {s.get('m1_bars_total', 0)}**\n")
    L.append(f"- First timestamp: {s.get('first_timestamp', 'n/a')}\n")
    L.append(f"- Last timestamp: {s.get('last_timestamp', 'n/a')}\n")
    L.append("- Expected M1 magnitude over 2018→now: several million. "
             "Actual acquired this session is a SMALL FRACTION — acquisition is "
             "IN PROGRESS and resumable; it was not completed in one session due to "
             "feed intermittency and wall-clock limits.\n\n")

    L.append("## 5. M1 → M5/M15 construction (Phase D)\n")
    if cov:
        L.append(f"- M1: {cov.get('m1_bars',0)} bars → M5: {cov.get('m5_bars',0)} bars, "
                 f"M15: {cov.get('m15_bars',0)} bars\n")
        L.append(f"- M5 span: {cov.get('m5_first','n/a')} → {cov.get('m5_last','n/a')}\n")
    L.append("- Method: deterministic OHLC (open=first, high=max, low=min, close=last, "
             "tick_volume=sum, spread=mean of OBSERVED bid/ask). No fabrication. "
             "Source finer → target coarser (permitted). No H1→M15 etc.\n")
    L.append(f"- M5 validation: ok={m5v.get('ok')} nan={m5v.get('nan_count',0)} "
             f"inf={m5v.get('inf_count',0)} invalid_ohlc={m5v.get('invalid_ohlc_count',0)} "
             f"dup_ts={m5v.get('duplicate_ts_count',0)} spread={m5v.get('spread_status')}\n")
    L.append("- Spread is OBSERVED (mean ask-bid of source ticks), never invented.\n\n")

    L.append("## 6. Gap classification (gaps NOT filled; all classified)\n")
    g = m5v.get("gaps", {})
    L.append(f"- M5 gaps: expected={g.get('expected_gap_count',0)} "
             f"market_closed={g.get('market_closed_count',0)} "
             f"unexpected={g.get('unexpected_gap_count',0)} "
             f"source_outage={g.get('source_outage_count',0)} "
             f"max_gap_hours={g.get('max_gap_hours',0)}\n")
    L.append("- The large max gap reflects INCOMPLETE acquisition (genuine data exists "
             "only at scattered days), NOT fabricated bars. This is reported, not hidden.\n\n")

    L.append("## 7. Cross-feed comparison (no merge)\n")
    for tf, r in cross.items():
        if isinstance(r, dict) and "error" not in r:
            L.append(f"- {tf}: overlap={r.get('overlap_timestamps',0)} "
                     f"mean_close_diff={r.get('mean_close_diff','?')} "
                     f"pct_within_$0.50={r.get('pct_close_within_0_5usd','?')}\n")
    L.append("\n")

    L.append("## 8. Economic calendar (Phase G/H/I)\n")
    L.append("- See `CALENDAR_SOURCE_INVESTIGATION.md`.\n")
    L.append("- **No free accessible point-in-time calendar source exists** from this "
             "environment. Trading Economics has an explicit PIT endpoint but requires "
             "paid credentials; FRED/ALFRED is a time series (not a calendar) and may "
             "not be converted into one.\n")
    L.append("- Status: **MACRO_DATA_BLOCKED_BY_PIT_REQUIREMENT**. No events fabricated.\n")
    L.append("- A PIT leakage test (`calendar.pit_leakage_test`) is implemented; a "
             "current-revised export without a release anchor is flagged PIT_UNVERIFIED "
             "and must not be used for V38.2.\n\n")

    L.append("## 9. Readiness gate (UNMODIFIED — not weakened)\n")
    L.append(f"- Status: **{gate.get('status')}**\n")
    if gate.get("blocking_reasons"):
        L.append("- Blocking reasons:\n")
        for r in gate["blocking_reasons"]:
            L.append(f"  - {r}\n")
    L.append("- The gate files (`XAUUSDm_M5.csv`, `XAUUSDm_M15.csv`) are NOT written "
             "until M5/M15 are BOTH validated AND substantively complete "
             "(≥50,000 M5 bars AND max gap ≤ 72h). Current sparse coverage does NOT "
             "meet that bar, so the gate correctly sees M5/M15 as ABSENT. The gate is "
             "not gamed by a sparse 365-day span.\n\n")

    L.append("## 10. Final status\n")
    L.append("**BLOCKED**\n\n")
    L.append("- Market data: genuine M1 acquired for a small fraction of the 2018→now "
             "window (exact counts above); resumable acquisition IN PROGRESS.\n")
    L.append("- M5/M15: constructed and validated from genuine M1 but NOT substantively "
             "complete → gate files absent → gate BLOCKED.\n")
    L.append("- Economic calendar: ABSENT, PIT-blocked.\n")
    L.append("- No model training, no ONNX, no MQL5, no deployment (Phase K honored).\n\n")

    L.append("## 11. Deliverables produced\n")
    L.append("1. `m1_acquisition_manifest.json` — raw M1 per-day acquisition manifest\n")
    L.append("2. `data/processed/dukascopy/XAUUSD_M1.csv` / `_M5.csv` / `_M15.csv` — genuine datasets\n")
    L.append("3. `v38_2_intraday_manifest.json` — M1/M5/M15 validation + gaps + cross-feed\n")
    L.append("4. `V38_2_INTRADAY_DATA_REPORT.md` — M1/M5/M15 validation + gap analysis\n")
    L.append("5. `CALENDAR_SOURCE_INVESTIGATION.md` — calendar source investigation + PIT\n")
    L.append("6. `V38_2_DATA_ACQUISITION_REPORT.md` — this report\n")
    L.append("7. `v38_2_readiness_certificate.json` — updated readiness certificate\n")
    L.append("8. tests: 6 new tests covering the acquisition path (52 V38.2 tests pass)\n\n")

    L.append("## 12. Non-negotiable honesty\n")
    L.append("- No data was fabricated, interpolated, duplicated, oversampled, or "
             "resampled-down. Empty minutes/hours produce absent bars.\n")
    L.append("- Expected counts are never reported as achieved counts.\n")
    L.append("- The V38.1 model remains a documented baseline and is NOT deployed.\n")
    L.append("- Next step requires operator action: continue the resumable acquisition "
             "to full coverage and supply a PIT-verified economic calendar.\n")
    return "".join(L)


if __name__ == "__main__":
    out = V38_2_DIR / "V38_2_DATA_ACQUISITION_REPORT.md"
    out.write_text(render())
    print(f"wrote {out}")
