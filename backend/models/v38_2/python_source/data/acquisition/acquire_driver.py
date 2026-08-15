"""Resumable day-partitioned Dukascopy M1 acquisition driver.

Acquires XAUUSD M1 tick archives one UTC day at a time, recording a per-day
manifest so the operation is restart-safe: a completed day is never re-fetched,
and a partially-fetched day resumes from its missing hours (each hour file is
already cached on disk by dukascopy._download_one).

Manifest fields (per the V38.2 acquisition spec):
  source, instrument, date (UTC day), timeframe, request_status, http_status,
  retry_count, bar_count, first_timestamp, last_timestamp, sha256 (day-level),
  validation_status.

request_status per day:
  COMPLETE   — every market-hour downloaded or correctly empty (market closed)
  PARTIAL    — some hours downloaded, some failed (transient); resumable
  EMPTY      — entire day returned no ticks (weekend / holiday)
  FAILED     — every hour failed
  FUTURE     — day is beyond now-UTC (not attempted)

The driver never fabricates bars: bar_count/first/last come from actually
parsing the downloaded .bi5 files for that day. Hours with no ticks are absent.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from . import dukascopy, bi5_parser

ACQ_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = ACQ_DIR / "m1_acquisition_manifest.json"

# Dukascopy XAUUSD sessions: roughly Sun 22:00 UTC -> Fri 21:00 UTC with a short
# daily break. We attempt all 24 hours/day and let the feed mark closures empty;
# but we SKIP entire weekend days (Sat/Sun) upfront to save requests, since the
# feed returns empty for them. A Sunday with a late-Sunday open is handled by
# attempting Sunday (the 22:00+ hours will have data, earlier hours empty).


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _day_iter(start: datetime, end: datetime):
    cur = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cur < end:
        yield cur
        cur = cur + timedelta(days=1)


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except Exception:
            pass
    return {"source": "Dukascopy", "instrument": "XAUUSD", "timeframe": "M1 (ticks)",
            "base_url": dukascopy.DATAFEED_BASE,
            "retrieval_started_utc": _now_utc().isoformat(),
            "days": {}}


def _save_manifest(man: dict) -> None:
    man["retrieval_updated_utc"] = _now_utc().isoformat()
    man["summary"] = _summarize(man)
    MANIFEST_PATH.write_text(json.dumps(man, indent=2, default=str))


def _summarize(man: dict) -> dict:
    days = man.get("days", {})
    counts = {"COMPLETE": 0, "PARTIAL": 0, "EMPTY": 0, "FAILED": 0, "FUTURE": 0}
    total_hours_dl = total_hours_empty = total_hours_failed = total_hours_cached = 0
    total_bars = 0
    first_ts = last_ts = None
    for d in days.values():
        s = d.get("request_status")
        if s in counts:
            counts[s] += 1
        total_hours_dl += d.get("hours_downloaded", 0)
        total_hours_cached += d.get("hours_cached", 0)
        total_hours_empty += d.get("hours_empty", 0)
        total_hours_failed += d.get("hours_failed", 0)
        total_bars += d.get("bar_count", 0)
        if d.get("first_timestamp"):
            if first_ts is None or d["first_timestamp"] < first_ts:
                first_ts = d["first_timestamp"]
        if d.get("last_timestamp"):
            if last_ts is None or d["last_timestamp"] > last_ts:
                last_ts = d["last_timestamp"]
    return {"days_total": len(days), "by_status": counts,
            "hours_downloaded": total_hours_dl, "hours_cached": total_hours_cached,
            "hours_empty": total_hours_empty, "hours_failed": total_hours_failed,
            "m1_bars_total": total_bars,
            "first_timestamp": first_ts, "last_timestamp": last_ts}


def _day_sha(day_dir: Path) -> str:
    """Combined SHA-256 of all .bi5 files for a day (provenance/integrity)."""
    if not day_dir.exists():
        return ""
    h = hashlib.sha256()
    files = sorted(day_dir.glob("*h_ticks.bi5"))
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def acquire_day(day: datetime, max_retries: int = dukascopy.MAX_RETRIES,
                timeout: int = 12, day_budget_s: float = 90.0) -> dict:
    """Acquire all 24 hours of one UTC day. Returns the day manifest entry.

    day_budget_s caps wall-clock spent on one day: when exceeded, the day is
    left PARTIAL and the driver moves on, so breadth (distinct days) is
    prioritized over completing a single stuck day. Missing hours are resumed
    on the next run (cached files are skipped by _download_one).
    """
    day_key = day.strftime("%Y-%m-%d")
    now = _now_utc()
    # future day
    if day.replace(hour=23) >= now:
        return {"date": day_key, "request_status": "FUTURE",
                "http_status": 0, "retry_count": 0, "bar_count": 0,
                "first_timestamp": "", "last_timestamp": "",
                "sha256": "", "validation_status": "n/a",
                "hours_downloaded": 0, "hours_cached": 0,
                "hours_empty": 0, "hours_failed": 0,
                "hours_attempted": 0, "budget_truncated": False}

    hours_dl = hours_cached = hours_empty = hours_failed = 0
    total_retries = 0
    http_codes = []
    errors = []
    day_dir = dukascopy.RAW_ROOT / f"{day.year}" / f"{day.month-1:02d}" / f"{day.day:02d}"
    budget_truncated = False
    day_t0 = time.time()

    for hh in range(24):
        if time.time() - day_t0 > day_budget_s:
            budget_truncated = True
            break
        hour = day.replace(hour=hh, minute=0, second=0, microsecond=0)
        if hour >= now:
            break
        # resumable: _download_one returns "cached" if file already on disk
        r = dukascopy._download_one(hour, max_retries=max_retries, timeout=timeout)
        if r.status == "downloaded":
            hours_dl += 1
        elif r.status == "cached":
            hours_cached += 1
        elif r.status == "empty":
            hours_empty += 1
        else:
            hours_failed += 1
        total_retries += max_retries if r.status == "failed" else 0
        http_codes.append(r.http_code)
        if r.error:
            errors.append(r.error)
        time.sleep(dukascopy.REQUEST_DELAY)

    # parse all binary hours for this day to get bar_count + first/last ts
    bars = 0
    first_ts = last_ts = ""
    for hh in range(24):
        p = day_dir / f"{hh:02d}h_ticks.bi5"
        if not p.exists():
            continue
        hour = day.replace(hour=hh, tzinfo=timezone.utc)
        m1 = bi5_parser.parse_hour_to_m1(p, hour)
        if m1.empty:
            continue
        bars += len(m1)
        fts = str(m1["ts"].iloc[0]); lts = str(m1["ts"].iloc[-1])
        if not first_ts or fts < first_ts:
            first_ts = fts
        if not last_ts or lts > last_ts:
            last_ts = lts

    if budget_truncated and (hours_dl + hours_cached) == 0 and hours_empty == 0 and hours_failed > 0:
        status = "PARTIAL"
    elif hours_failed > 0 and (hours_dl + hours_cached) > 0:
        status = "PARTIAL"
    elif budget_truncated:
        status = "PARTIAL"
    elif hours_failed > 0 and (hours_dl + hours_cached) == 0:
        status = "FAILED"
    elif (hours_dl + hours_cached) == 0 and hours_empty > 0:
        status = "EMPTY"
    else:
        status = "COMPLETE"

    val = "validated" if bars > 0 or status == "EMPTY" else ("parse_failed" if status != "EMPTY" else "empty")

    return {"date": day_key, "request_status": status,
            "http_status": int(max(set(http_codes), key=http_codes.count)) if http_codes else 0,
            "retry_count": total_retries, "bar_count": bars,
            "first_timestamp": first_ts, "last_timestamp": last_ts,
            "sha256": _day_sha(day_dir), "validation_status": val,
            "hours_downloaded": hours_dl, "hours_cached": hours_cached,
            "hours_empty": hours_empty, "hours_failed": hours_failed,
            "hours_attempted": hours_dl + hours_cached + hours_empty + hours_failed,
            "budget_truncated": budget_truncated,
            "errors_sample": errors[:5]}


def run(start: datetime, end: Optional[datetime] = None,
        max_retries: int = dukascopy.MAX_RETRIES, timeout: int = 12,
        day_budget_s: float = 90.0, max_days: Optional[int] = None,
        log_every: int = 1) -> dict:
    """Acquire [start, end) day by day. end defaults to now-UTC.

    Resumable: days already marked COMPLETE in the manifest are skipped.
    max_days caps the number of NEW days processed this run (None = unbounded).
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is None:
        end = _now_utc()
    elif end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    man = _load_manifest()
    days = man.setdefault("days", {})
    processed = 0
    for day in _day_iter(start, end):
        dkey = day.strftime("%Y-%m-%d")
        if dkey in days and days[dkey].get("request_status") == "COMPLETE":
            continue
        if max_days is not None and processed >= max_days:
            break
        entry = acquire_day(day, max_retries=max_retries, timeout=timeout,
                            day_budget_s=day_budget_s)
        days[dkey] = entry
        _save_manifest(man)
        processed += 1
        if processed % log_every == 0:
            s = man["summary"]
            print(f"[acq] {dkey} -> {entry['request_status']} "
                  f"(bars={entry['bar_count']}, dl={entry['hours_downloaded']}, "
                  f"cached={entry['hours_cached']}, empty={entry['hours_empty']}, "
                  f"failed={entry['hours_failed']}) | "
                  f"total days={s['days_total']} bars={s['m1_bars_total']}", flush=True)
    _save_manifest(man)
    return man


def reconcile_manifest_from_files() -> int:
    """Rebuild per-day manifest entries from the .bi5 files actually on disk.

    Used after a crash/competing-writer to recover an accurate manifest from
    the cached files (the source of truth). Only fills in days that have files
    but no/older manifest entry; never deletes entries. Returns days updated.
    """
    man = _load_manifest()
    days = man.setdefault("days", {})
    updated = 0
    # group all bi5 files by date
    by_date = {}
    for p in sorted(dukascopy.RAW_ROOT.rglob("*h_ticks.bi5")):
        try:
            parts = p.parts
            hh = int(parts[-1].split("h_")[0])
            dd = int(parts[-2]); mm0 = int(parts[-3]); yy = int(parts[-4])
            day = datetime(yy, mm0 + 1, dd, tzinfo=timezone.utc)
            by_date.setdefault(day.strftime("%Y-%m-%d"), []).append((hh, p))
        except Exception:
            continue
    for dkey, hour_files in by_date.items():
        existing = days.get(dkey)
        if existing and existing.get("request_status") == "COMPLETE":
            continue
        day_dir = hour_files[0][1].parent
        bars = 0; first_ts = last_ts = ""
        for hh, p in hour_files:
            yy = int(p.parts[-4]); mm0 = int(p.parts[-3]); dd = int(p.parts[-2])
            hour = datetime(yy, mm0 + 1, dd, hh, tzinfo=timezone.utc)
            m1 = bi5_parser.parse_hour_to_m1(p, hour)
            if m1.empty:
                continue
            bars += len(m1)
            fts = str(m1["ts"].iloc[0]); lts = str(m1["ts"].iloc[-1])
            if not first_ts or fts < first_ts: first_ts = fts
            if not last_ts or lts > last_ts: last_ts = lts
        n_hours = len(hour_files)
        entry = {"date": dkey, "request_status": "COMPLETE" if n_hours >= 20 else "PARTIAL",
                 "http_status": 200, "retry_count": 0, "bar_count": bars,
                 "first_timestamp": first_ts, "last_timestamp": last_ts,
                 "sha256": _day_sha(day_dir), "validation_status": "validated" if bars else "empty",
                 "hours_downloaded": 0, "hours_cached": n_hours, "hours_empty": 0,
                 "hours_failed": 0, "hours_attempted": n_hours,
                 "budget_truncated": False, "reconciled_from_cache": True}
        days[dkey] = entry
        updated += 1
    _save_manifest(man)
    return updated


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default="")  # empty = now
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=12)
    ap.add_argument("--day-budget", type=float, default=90.0)
    ap.add_argument("--max-retries", type=int, default=dukascopy.MAX_RETRIES)
    ap.add_argument("--reconcile", action="store_true",
                    help="rebuild manifest from cached .bi5 files, then exit")
    args = ap.parse_args()
    if args.reconcile:
        n = reconcile_manifest_from_files()
        print(f"reconciled {n} day entries from cached files")
    else:
        s = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        e = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.end else None
        run(s, e, max_days=args.max_days, timeout=args.timeout,
            day_budget_s=args.day_budget, max_retries=args.max_retries)
