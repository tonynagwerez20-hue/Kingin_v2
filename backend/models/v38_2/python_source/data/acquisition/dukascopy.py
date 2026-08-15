"""Dukascopy .bi5 M1 tick downloader.

Dukascopy publishes historical tick data as LZ4-compressed .bi5 archives, one
per (instrument, year, month, day, hour), at:

    https://datafeed.dukascopy.com/datafeed/{INSTRUMENT}/{YEAR}/{MONTH0}/{DAY}/{HH}h_ticks.bi5

Month is zero-indexed. Hours are 00..23 UTC. An empty/non-existent hour returns
a small HTML 404 page (not binary) — detected and treated as "no ticks that
hour" (a market-closure period), never fabricated.

This module is resumable: each hour is downloaded once to
data/raw/dukascopy/xauusd/m1/{Y}/{M0:02d}/{D:02d}/{HH}h_ticks.bi5 and skipped on
re-run if the SHA-256 matches the manifest. Retries with backoff. No data is
loaded into RAM in bulk — files are streamed to disk.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import urllib.request
import urllib.error

DATAFEED_BASE = "https://datafeed.dukascopy.com/datafeed"
RAW_ROOT = Path(__file__).resolve().parents[4] / "data" / "raw" / "dukascopy" / "xauusd" / "m1"
INSTRUMENT = "XAUUSD"
# Dukascopy's CDN intermittently returns 503 / timeouts (rate-limiting). A robust
# downloader needs many retries with growing backoff. These are tuned for the
# observed flakiness: some hours succeed on attempt 1, others need 5-8 attempts.
MAX_RETRIES = 8
RETRY_BACKOFF = [1, 2, 3, 5, 8, 12, 20, 30]  # seconds
REQUEST_DELAY = 0.15  # gentle inter-request delay to avoid triggering 503 bursts
PROBE_TIMEOUT = 12  # seconds per request during feasibility probe
PROBE_MAX_RETRIES = 3  # fail fast during probe


@dataclass
class DownloadResult:
    hour_key: str  # "2024-01-02T14"
    url: str
    path: Path
    status: str  # "downloaded" | "cached" | "empty" | "failed"
    http_code: int
    size_bytes: int
    sha256: str
    elapsed_s: float
    error: str = ""


@dataclass
class DownloadLog:
    instrument: str
    base_url: str
    retrieval_time_utc: str
    results: list = field(default_factory=list)
    cached_count: int = 0
    downloaded_count: int = 0
    empty_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict:
        return {"instrument": self.instrument, "base_url": self.base_url,
                "retrieval_time_utc": self.retrieval_time_utc,
                "summary": {"downloaded": self.downloaded_count, "cached": self.cached_count,
                            "empty": self.empty_count, "failed": self.failed_count},
                "results": [r.__dict__ for r in self.results]}


def _url_for(dt_hour: datetime) -> str:
    return (f"{DATAFEED_BASE}/{INSTRUMENT}/{dt_hour.year}/"
            f"{dt_hour.month - 1:02d}/{dt_hour.day:02d}/{dt_hour.hour:02d}h_ticks.bi5")


def _path_for(dt_hour: datetime) -> Path:
    return RAW_ROOT / f"{dt_hour.year}" / f"{dt_hour.month - 1:02d}" / f"{dt_hour.day:02d}" / f"{dt_hour.hour:02d}h_ticks.bi5"


def _is_binary_bi5(data: bytes) -> bool:
    """A real .bi5 is LZ4-framed binary. HTML 404/landing pages start with '<'."""
    if len(data) < 4:
        return False
    if data[:1] == b"<":
        return False
    return True


def _download_one(dt_hour: datetime, max_retries: int = MAX_RETRIES,
                  timeout: int = 30) -> DownloadResult:
    url = _url_for(dt_hour)
    path = _path_for(dt_hour)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = f"{dt_hour.strftime('%Y-%m-%d')}T{dt_hour.hour:02d}"

    # resumable: if already present with a recorded hash, skip
    if path.exists():
        existing = path.read_bytes()
        if _is_binary_bi5(existing):
            return DownloadResult(key, url, path, "cached", 200, len(existing),
                                  hashlib.sha256(existing).hexdigest(), 0.0)

    last_err = ""
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                data = resp.read()
            if not _is_binary_bi5(data):
                # HTML 404 / landing / empty hour — not binary. Record as empty.
                return DownloadResult(key, url, path, "empty", code, len(data), "", time.time() - t0,
                                      "non-binary response (market closure or 404)")
            path.write_bytes(data)
            return DownloadResult(key, url, path, "downloaded", code, len(data),
                                  hashlib.sha256(data).hexdigest(), time.time() - t0)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.reason}"
            if e.code == 404:
                # genuine market-closure / no-data hour — not retried
                return DownloadResult(key, url, path, "empty", e.code, 0, "", time.time() - t0, last_err)
            # 503 and other 5xx are intermittent — retry with backoff below
        except urllib.error.URLError as e:
            last_err = f"URLError: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < max_retries - 1:
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
    return DownloadResult(key, url, path, "failed", 0, 0, "", 0.0, last_err)


def download_hours(start: datetime, end: datetime,
                   log_path: Optional[Path] = None,
                   max_retries: int = MAX_RETRIES,
                   timeout: int = 20) -> DownloadLog:
    """Download every UTC hour in [start, end) inclusive of start's day.

    start/end are timezone-aware UTC datetimes. Iterates hour by hour.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    log = DownloadLog(instrument=INSTRUMENT, base_url=DATAFEED_BASE,
                      retrieval_time_utc=datetime.now(timezone.utc).isoformat())
    cur = start.replace(minute=0, second=0, microsecond=0)
    while cur < end:
        r = _download_one(cur, max_retries=max_retries, timeout=timeout)
        log.results.append(r)
        if r.status == "downloaded":
            log.downloaded_count += 1
        elif r.status == "cached":
            log.cached_count += 1
        elif r.status == "empty":
            log.empty_count += 1
        else:
            log.failed_count += 1
        # advance one hour
        from datetime import timedelta
        cur = cur + timedelta(hours=1)
        time.sleep(REQUEST_DELAY)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(log.to_dict(), indent=2, default=str))
    return log


def probe(endpoints: list) -> dict:
    """Probe a list of sample hour datetimes to verify feed reachability.

    Returns a dict summarizing reachability without doing a full download.
    Used by the pipeline to decide whether acquisition is feasible at all.
    """
    from datetime import timedelta
    out = {"reachable": False, "binary_sample": False, "attempts": []}
    for dt in endpoints:
        r = _download_one(dt, max_retries=PROBE_MAX_RETRIES, timeout=PROBE_TIMEOUT)
        out["attempts"].append({"hour": r.hour_key, "status": r.status,
                                "http_code": r.http_code, "size": r.size_bytes,
                                "error": r.error})
        if r.status in ("downloaded", "cached"):
            out["reachable"] = True
            out["binary_sample"] = True
            break
    return out
