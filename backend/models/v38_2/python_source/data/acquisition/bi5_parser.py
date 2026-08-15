"""Dukascopy .bi5 tick parser -> M1 OHLCV.

A .bi5 file is an **LZMA**-compressed stream of fixed-size tick records
(Dukascopy's bi5 format — NOT LZ4, despite the .bi5 name). Each tick record is
**20 bytes, big-endian** `>3I2f`:

    struct tick { uint32 millisecs; uint32 ask; uint32 bid;
                  float32 ask_volume; float32 bid_volume; }

The base timestamp is the hour of the file (UTC). `millisecs` is the offset in
milliseconds from the top of that hour. Prices for XAUUSD are stored as
integer price*1000 (3 decimal places): real_price = raw / 1000.

This module produces M1 OHLCV bars from the parsed ticks. No interpolation: a
minute with no ticks produces no bar (the bar is absent, not fabricated).

spread: the source is a tick feed with bid/ask, so the per-bar spread is the
mean (ask - bid) of ticks in that minute — an OBSERVED spread, not invented.
If a future source lacks bid/ask, the aggregator records spread=UNAVAILABLE.
"""
from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

# Dukascopy XAUUSD price factor: stored integer * 1000 = real price (3 decimals).
XAUUSD_PRICE_FACTOR = 1000.0
TICK_STRUCT = struct.Struct(">3I2f")  # 20 bytes, big-endian
TICK_SIZE = TICK_STRUCT.size


@dataclass
class ParsedHour:
    hour: datetime  # UTC, tz-aware
    n_ticks: int
    first_tick: Optional[datetime]
    last_tick: Optional[datetime]


def parse_bi5_file(path: Path, hour: datetime) -> pd.DataFrame:
    """Parse one .bi5 hour file into a tick DataFrame.

    Returns columns: ts(UTC), bid, ask, bid_vol, ask_vol.
    Returns empty DataFrame if the file is missing/corrupt (no fabrication).
    """
    if not path.exists():
        return pd.DataFrame(columns=["ts", "bid", "ask", "bid_vol", "ask_vol"])
    raw = path.read_bytes()
    if len(raw) < 8 or raw[:1] == b"<":
        # HTML 404 / landing page — not binary tick data
        return pd.DataFrame(columns=["ts", "bid", "ask", "bid_vol", "ask_vol"])
    try:
        data = lzma.decompress(raw)
    except Exception:
        return pd.DataFrame(columns=["ts", "bid", "ask", "bid_vol", "ask_vol"])
    n = len(data) // TICK_SIZE
    if n == 0:
        return pd.DataFrame(columns=["ts", "bid", "ask", "bid_vol", "ask_vol"])
    ts_list = []
    bid = []; ask = []; bvol = []; avol = []
    base = hour.replace(minute=0, second=0, microsecond=0)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    for i in range(n):
        off = i * TICK_SIZE
        ms, a, b, av, bv = TICK_STRUCT.unpack_from(data, off)
        ts_list.append(base + timedelta(milliseconds=int(ms)))
        ask.append(a / XAUUSD_PRICE_FACTOR)
        bid.append(b / XAUUSD_PRICE_FACTOR)
        avol.append(float(av)); bvol.append(float(bv))
    return pd.DataFrame({"ts": ts_list, "bid": bid, "ask": ask,
                         "bid_vol": bvol, "ask_vol": avol})


def ticks_to_m1(ticks: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ticks into 1-minute OHLCV bars.

    open/high/low/close from mid-price (bid+ask)/2? No — for an execution feed
    we keep both bid and ask OHLC, but the V38.2 bar schema expects a single
    OHLC. We use the MID price for OHLC and record observed_spread = mean(ask-bid).
    tick_volume = number of ticks in the minute (true count, not invented).
    Bars with zero ticks are absent (never fabricated).
    """
    if ticks.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close",
                                     "tick_volume", "spread"])
    df = ticks.copy()
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["spread"] = (df["ask"] - df["bid"])
    df["minute"] = df["ts"].dt.floor("min")
    g = df.groupby("minute")
    out = pd.DataFrame({
        "ts": list(g.groups.keys()),
        "open": g["mid"].first().to_numpy(),
        "high": g["mid"].max().to_numpy(),
        "low": g["mid"].min().to_numpy(),
        "close": g["mid"].last().to_numpy(),
        "tick_volume": g.size().to_numpy(),
        "spread": g["spread"].mean().to_numpy(),
    })
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out[["ts", "open", "high", "low", "close", "tick_volume", "spread"]]


def parse_hour_to_m1(path: Path, hour: datetime) -> pd.DataFrame:
    ticks = parse_bi5_file(path, hour)
    return ticks_to_m1(ticks)
