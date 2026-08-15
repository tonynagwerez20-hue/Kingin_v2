"""ALFRED (FRED) vintage indicator query module.

Queries FRED/ALFRED vintage data using the fredgraph CSV endpoint with
vintage_date parameter. This retrieves the value of an indicator AS IT WAS
KNOWN on a given date — i.e., the genuine point-in-time vintage value, before
any subsequent revisions.

No API key needed for the fredgraph CSV endpoint:
  https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES&cosd=START&coed=END&vintage_date=DATE

Uses curl subprocess for HTTP requests (Python urllib has TLS timeout issues
with fred.stlouisfed.org in this environment).

This module does NOT convert ALFRED observations into calendar events
(forbidden). It uses ALFRED only as a cross-check of FF actual/previous values.
"""
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
# FRED blocks some browser-like UAs; use a simple curl UA
FRED_UA = "curl/8.0"

VINTAGE_CACHE_DIR = Path(__file__).resolve().parents[4] / "data" / "fred_raw"


def _curl_fred_csv(url: str) -> str:
    """Fetch a URL via curl subprocess. Returns the response body as string."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-A", FRED_UA, url],
            capture_output=True, text=True, timeout=25)
        return result.stdout
    except Exception:
        return ""


def _fetch_vintage_csv(series_id: str, obs_start: str, obs_end: str,
                       vintage_date: str, cache: bool = True) -> pd.DataFrame:
    """Fetch a FRED vintage CSV for a given series and vintage date."""
    VINTAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = (VINTAGE_CACHE_DIR /
                  f"{series_id}_vintage_{vintage_date}_{obs_start}_{obs_end}.csv")
    if cache and cache_file.exists():
        return pd.read_csv(cache_file)

    url = (f"{FRED_CSV_URL}?id={series_id}&cosd={obs_start}&coed={obs_end}"
           f"&vintage_date={vintage_date}")
    data = _curl_fred_csv(url)

    lines = data.strip().split("\n")
    if len(lines) < 2:
        return pd.DataFrame()
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            rows.append({"observation_date": parts[0], series_id: parts[1]})

    df = pd.DataFrame(rows)
    if not df.empty:
        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        if cache:
            df.to_csv(cache_file, index=False)
    time.sleep(0.3)
    return df


def _fetch_current_csv(series_id: str, obs_start: str, obs_end: str,
                       cache: bool = True) -> pd.DataFrame:
    """Fetch the CURRENT (latest-revised) values for a FRED series."""
    VINTAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = VINTAGE_CACHE_DIR / f"{series_id}_current_{obs_start}_{obs_end}.csv"
    if cache and cache_file.exists():
        return pd.read_csv(cache_file)

    url = f"{FRED_CSV_URL}?id={series_id}&cosd={obs_start}&coed={obs_end}"
    data = _curl_fred_csv(url)

    lines = data.strip().split("\n")
    if len(lines) < 2:
        return pd.DataFrame()
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            rows.append({"observation_date": parts[0], series_id: parts[1]})

    df = pd.DataFrame(rows)
    if not df.empty:
        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        if cache:
            df.to_csv(cache_file, index=False)
    time.sleep(0.3)
    return df


def query_alfred_vintage(series_id: str, obs_date: str,
                         vintage_date: str, cache: bool = True) -> dict:
    """Query the ALFRED vintage value for a single observation date.

    Returns: {
        "series_id": str,
        "obs_date": str,
        "vintage_date": str,
        "vintage_value": float | None,   # as-of-T value
        "current_value": float | None,   # latest-revised value
        "revised": bool,                  # True if vintage != current
        "available": bool,
    }
    """
    if series_id is None:
        return {"series_id": None, "obs_date": obs_date, "vintage_date": vintage_date,
                "vintage_value": None, "current_value": None,
                "revised": False, "available": False}

    obs_start = obs_date
    obs_end = obs_date

    vintage_df = _fetch_vintage_csv(series_id, obs_start, obs_end, vintage_date, cache)
    current_df = _fetch_current_csv(series_id, obs_start, obs_end, cache)

    vintage_val = None
    current_val = None

    if not vintage_df.empty:
        row = vintage_df[vintage_df["observation_date"] == obs_date]
        if not row.empty:
            vintage_val = row[series_id].iloc[0]

    if not current_df.empty:
        row = current_df[current_df["observation_date"] == obs_date]
        if not row.empty:
            current_val = row[series_id].iloc[0]

    revised = (vintage_val is not None and current_val is not None
               and not pd.isna(vintage_val) and not pd.isna(current_val)
               and abs(vintage_val - current_val) > 1e-9)

    return {
        "series_id": series_id,
        "obs_date": obs_date,
        "vintage_date": vintage_date,
        "vintage_value": vintage_val,
        "current_value": current_val,
        "revised": revised,
        "available": vintage_val is not None and not pd.isna(vintage_val),
    }


def query_vintage_for_event(series_id: str, event_ts: datetime,
                            obs_date: str, cache: bool = True) -> dict:
    """Query ALFRED vintage for a calendar event.

    The vintage_date is set to the event release date (event_ts date) — this
    retrieves the value as it was known on the day of the release.
    """
    vintage_date = event_ts.strftime("%Y-%m-%d")
    return query_alfred_vintage(series_id, obs_date, vintage_date, cache)
