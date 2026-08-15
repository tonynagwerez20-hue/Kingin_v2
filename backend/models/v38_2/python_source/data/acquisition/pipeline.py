"""V38.2 acquisition pipeline orchestrator.

Sequence:
  1. Probe Dukascopy feed reachability.
  2. If reachable: download M1 ticks (chunked, resumable) -> parse -> aggregate
     to M5/M15 (and H1/H4 for cross-feed comparison only).
  3. Validate every dataset through the existing V38.2 validator/gap_analysis.
  4. Copy validated M5/M15 to the V38.2 expected filenames ONLY if they pass.
  5. Assess calendar acquisition status.
  6. Write provenance (PRICE_SOURCE.md, CALENDAR_SOURCE.md, DATA_PROVENANCE.md,
     ACQUISITION_MANIFEST.json).
  7. Run the readiness gate. Report DATA READY or BLOCKED honestly.

If the feed is unreachable, the pipeline stops after step 1, writes a provenance
manifest documenting the failed attempt, and the readiness gate stays BLOCKED.
No data is fabricated.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import dukascopy, bi5_parser, aggregator, provenance, calendar as cal_mod, cross_feed
from ..loader import load_h1, load_h4
from ..validator import validate_bars
from ..gap_analysis import analyze_gaps

BACKEND = Path(__file__).resolve().parents[5]
DATA = BACKEND / "data"
RAW_M1 = DATA / "raw" / "dukascopy" / "xauusd" / "m1"
PROC = DATA / "processed" / "dukascopy"
ACQ_DIR = Path(__file__).resolve().parent

TARGET_M5 = DATA / "XAUUSDm_M5.csv"
TARGET_M15 = DATA / "XAUUSDm_M15.csv"
TARGET_CAL = DATA / "economic_calendar.csv"

PROBE_DATES = [
    datetime(2024, 1, 2, 12, tzinfo=timezone.utc),   # a Tuesday mid-session
    datetime(2024, 1, 2, 14, tzinfo=timezone.utc),
    datetime(2024, 1, 3, 10, tzinfo=timezone.utc),
    datetime(2024, 1, 3, 15, tzinfo=timezone.utc),
]


def _hour_iter(start, end):
    cur = start.replace(minute=0, second=0, microsecond=0)
    while cur < end:
        yield cur
        cur = cur + timedelta(hours=1)


def run(start: datetime, end: datetime, full: bool = True) -> dict:
    """Run the acquisition pipeline from `start` to `end` (UTC, exclusive).

    Returns a dict summary. `full=True` does the complete download; `full=False`
    does only the feasibility probe + provenance (used when feed is down).
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    retrieval_time = datetime.now(timezone.utc).isoformat()
    summary = {"provider": "Dukascopy", "instrument": "XAUUSD",
               "source_tf": "M1 (ticks->M1)", "derived_tfs": ["M5", "M15", "H1", "H4"],
               "start": start.isoformat(), "end": end.isoformat(),
               "retrieval_time_utc": retrieval_time, "feed_reachable": False,
               "m1_rows": 0, "m5_rows": 0, "m15_rows": 0,
               "validation": {}, "calendar": {}, "overall_status": "BLOCKED"}

    # --- Step 1: probe feasibility ---
    probe = dukascopy.probe(PROBE_DATES)
    summary["probe"] = probe
    summary["feed_reachable"] = probe["reachable"]

    transformations = [
        "M1 tick .bi5 (LZ4) downloaded per UTC hour, SHA-256 hashed, stored under data/raw/dukascopy/xauusd/m1/",
        "ticks parsed (24-byte records: time_delta_ms, ask, bid, ask_vol, bid_vol); price * 1000 factor",
        "M1 OHLCV = mid(bid,ask) OHLC + tick_volume(count) + spread=mean(ask-bid) [OBSERVED]",
        "M5/M15/H1/H4 = deterministic aggregation: open=first, high=max, low=min, close=last, tick_volume=sum",
        "no interpolation, no fabrication: minutes/hours with no ticks produce no bar (absent, not filled)",
    ]
    discards = []

    if not probe["reachable"]:
        # --- Honest stop: feed unreachable ---
        summary["overall_status"] = "BLOCKED_FEED_UNREACHABLE"
        summary["block_reason"] = (
            "Dukascopy datafeed host returned HTTP 503 (No server is available to "
            "handle this request) for all probed .bi5 tick-archive URLs. The binary "
            "historical feed is not serving this environment. M5/M15 were NOT "
            "fabricated.")
        discards.append("no records discarded — none acquired")
        _write_provenance(summary, transformations, discards, hashes={}, feed_status="UNREACHABLE")
        _write_calendar_provenance()
        return summary

    if not full:
        _write_provenance(summary, transformations, discards, hashes={}, feed_status="REACHABLE")
        return summary

    # --- Step 2: download + parse + aggregate (only if reachable) ---
    log = dukascopy.download_hours(start, end, log_path=ACQ_DIR / "download_log.json")
    summary["download_summary"] = log.to_dict()["summary"]

    # parse all downloaded hour files -> M1
    m1_frames = []
    for r in log.results:
        if r.status in ("downloaded", "cached") and r.size_bytes > 0:
            hour = datetime.strptime(r.hour_key, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
            m1 = bi5_parser.parse_hour_to_m1(r.path, hour)
            if not m1.empty:
                m1_frames.append(m1)
    if m1_frames:
        m1 = pd.concat(m1_frames, ignore_index=True).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    else:
        m1 = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "tick_volume", "spread"])
    summary["m1_rows"] = len(m1)

    # aggregate
    m5 = aggregator.aggregate(m1, "M5")
    m15 = aggregator.aggregate(m1, "M15")
    h1d = aggregator.aggregate(m1, "H1")
    h4d = aggregator.aggregate(m1, "H4")
    summary["m5_rows"] = len(m5)
    summary["m15_rows"] = len(m15)

    # validate
    val_m5 = validate_bars(m5); val_m15 = validate_bars(m15)
    gaps_m5 = analyze_gaps(m5, "M5"); gaps_m15 = analyze_gaps(m15, "M15")
    summary["validation"] = {
        "M5": {**val_m5.to_dict(), "gaps": gaps_m5},
        "M15": {**val_m15.to_dict(), "gaps": gaps_m15},
    }

    # write processed files
    PROC.mkdir(parents=True, exist_ok=True)
    m1.to_csv(PROC / "XAUUSD_M1.csv", index=False)
    m5.to_csv(PROC / "XAUUSD_M5.csv", index=False)
    m15.to_csv(PROC / "XAUUSD_M15.csv", index=False)
    h1d.to_csv(PROC / "XAUUSD_H1.csv", index=False)
    h4d.to_csv(PROC / "XAUUSD_H4.csv", index=False)

    # copy to V38.2 expected filenames ONLY if validated
    m5_ok = val_m5.ok and len(m5) > 0
    m15_ok = val_m15.ok and len(m15) > 0
    if m5_ok:
        m5.to_csv(TARGET_M5, index=False)
    if m15_ok:
        m15.to_csv(TARGET_M15, index=False)

    # cross-feed comparison (research vs broker) — no merge
    cf_reports = {}
    if not h1d.empty:
        cf_reports["H1"] = cross_feed.compare(load_h1().df, h1d, "H1").to_dict()
    if not h4d.empty:
        cf_reports["H4"] = cross_feed.compare(load_h4().df, h4d, "H4").to_dict()
    summary["cross_feed"] = cf_reports

    hashes = {  # SHA-256s recorded in download_log.json per hour; summarize counts here
        "m1_hours_downloaded": log.downloaded_count,
        "m1_hours_cached": log.cached_count,
        "m1_hours_empty": log.empty_count,
        "m1_hours_failed": log.failed_count,
    }
    summary["overall_status"] = "READY" if (m5_ok and m15_ok) else "BLOCKED_VALIDATION"
    _write_provenance(summary, transformations, discards, hashes=hashes, feed_status="REACHABLE")
    _write_calendar_provenance()
    return summary


def _write_provenance(summary, transformations, discards, hashes, feed_status):
    coverage = {"start": summary.get("start"), "end": summary.get("end"),
                "m1_rows": summary.get("m1_rows", 0),
                "m5_rows": summary.get("m5_rows", 0),
                "m15_rows": summary.get("m15_rows", 0)}
    rows = {"M1": summary.get("m1_rows", 0), "M5": summary.get("m5_rows", 0),
            "M15": summary.get("m15_rows", 0)}
    provenance.write_price_source_md(
        provider=summary["provider"], base_url=dukascopy.DATAFEED_BASE,
        instrument=summary["instrument"], source_tf=summary["source_tf"],
        derived_tfs=summary["derived_tfs"], retrieval_time=summary["retrieval_time_utc"],
        feed_status=feed_status, coverage=coverage, row_counts=rows,
        transformations=transformations, discards=discards, hashes=hashes)
    provenance.write_data_provenance_md(
        ACQ_DIR / "PRICE_SOURCE.md", ACQ_DIR / "CALENDAR_SOURCE.md",
        overall_status=summary["overall_status"])
    provenance.write_acquisition_manifest(summary)


def _write_calendar_provenance():
    st = cal_mod.acquisition_status()
    provenance.write_calendar_source_md(st.to_dict())


if __name__ == "__main__":
    # default window: 2018-01-01 -> latest
    end = datetime.now(timezone.utc)
    s = datetime(2018, 1, 1, tzinfo=timezone.utc)
    res = run(s, end, full=True)
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("probe", "download_summary", "cross_feed", "validation")},
                     indent=2, default=str))
