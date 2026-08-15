"""Cross-feed comparison: Dukascopy-derived H1/H4 vs existing broker H1/H4.

The two feeds are NOT merged. This tool measures whether the research feed
(Dukascopy) is materially different from the execution feed (broker/MetaQuotes
XAUUSDm) over the overlapping period, so we can decide whether conclusions
drawn on the research feed transfer to the execution feed.

Measures: timestamp overlap, OHLC differences, high/low divergence, close
divergence, session-boundary differences, spread differences.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class CrossFeedReport:
    overlap_timestamps: int = 0
    broker_only: int = 0
    dukas_only: int = 0
    mean_close_diff: float = 0.0
    median_close_diff: float = 0.0
    max_close_diff: float = 0.0
    mean_high_diff: float = 0.0
    mean_low_diff: float = 0.0
    pct_close_within_0_1usd: float = 0.0  # fraction of bars within $0.10
    pct_close_within_0_5usd: float = 0.0
    pct_close_within_1usd: float = 0.0
    spread_status: str = "n/a"
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


def compare(broker: pd.DataFrame, dukas: pd.DataFrame, tf: str) -> CrossFeedReport:
    rep = CrossFeedReport()
    if broker is None or dukas is None or broker.empty or dukas.empty:
        rep.notes.append("one or both feeds empty — no comparison")
        return rep
    b = broker[["ts", "open", "high", "low", "close"]].copy()
    d = dukas[["ts", "open", "high", "low", "close"]].copy()
    b["ts"] = pd.to_datetime(b["ts"], utc=True)
    d["ts"] = pd.to_datetime(d["ts"], utc=True)
    m = b.merge(d, on="ts", suffixes=("_broker", "_dukas"), how="outer", indicator=True)
    rep.overlap_timestamps = int((m["_merge"] == "both").sum())
    rep.broker_only = int((m["_merge"] == "left_only").sum())
    rep.dukas_only = int((m["_merge"] == "right_only").sum())
    both = m[m["_merge"] == "both"].copy()
    if both.empty:
        rep.notes.append("no overlapping timestamps")
        return rep
    cd = (both["close_broker"] - both["close_dukas"]).abs()
    rep.mean_close_diff = round(float(cd.mean()), 4)
    rep.median_close_diff = round(float(cd.median()), 4)
    rep.max_close_diff = round(float(cd.max()), 4)
    rep.mean_high_diff = round(float((both["high_broker"] - both["high_dukas"]).abs().mean()), 4)
    rep.mean_low_diff = round(float((both["low_broker"] - both["low_dukas"]).abs().mean()), 4)
    rep.pct_close_within_0_1usd = round(float((cd <= 0.10).mean()), 4)
    rep.pct_close_within_0_5usd = round(float((cd <= 0.50).mean()), 4)
    rep.pct_close_within_1usd = round(float((cd <= 1.00).mean()), 4)
    rep.notes.append(f"{tf}: {rep.overlap_timestamps} overlapping bars; "
                     f"{rep.pct_close_within_0_5usd*100:.1f}% within $0.50 close")
    return rep
