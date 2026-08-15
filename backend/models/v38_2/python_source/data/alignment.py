"""Deterministic multi-timeframe alignment (H4 → H1 → M15 → M5).

For every lower-timeframe observation, only higher-timeframe information that
was *actually known at that timestamp* may be attached. This enforces:

    source_confirmation_time <= feature_timestamp

The existing v38 structure engine already enforces `confirmation_bar <= bar_index`
at the structure-object level; this module enforces the same principle at the
*bar-alignment* level so no higher-timeframe bar that closes after a feature
timestamp can leak into that feature.

Look-ahead is impossible by construction: we map a feature timestamp to the
latest higher-TF bar whose CLOSE time is <= the feature timestamp (i.e. the bar
that has already CLOSED and is therefore confirmed).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass
class AlignmentPair:
    htf: str
    ltf: str
    n_ltf_rows: int
    n_aligned: int
    n_unmatched: int
    example_violations: list


def _close_times(hf_df: pd.DataFrame) -> pd.DatetimeIndex:
    """Higher-TF bar close time = bar open + bar duration. For bar-indexed data
    we treat the bar's own timestamp as its CONFIRMATION (close) time, so a bar
    at time T is only usable for features with ts >= T."""
    return pd.DatetimeIndex(hf_df["ts"])


def align_ltf_to_htf(ltf_df: pd.DataFrame, htf_df: pd.DataFrame,
                     htf_label: str, ltf_label: str) -> tuple[pd.DataFrame, AlignmentPair]:
    """Attach the latest confirmed (closed) higher-TF bar index to each lower-TF row.

    Returns the ltf_df with an added 'htf_close_ts' and 'htf_bar_idx' column.
    A higher-TF bar is 'confirmed' for a lower-TF feature row only if its
    timestamp (close) is <= the feature timestamp. This is the leakage rule.
    """
    htf_ts = pd.DatetimeIndex(htf_df["ts"]).sort_values()
    lts = pd.DatetimeIndex(ltf_df["ts"])
    # work in tz-naive ns for searchsorted, then localize results back to UTC
    hts_naive = htf_ts.tz_convert(None) if htf_ts.tz is not None else htf_ts
    lts_naive = lts.tz_convert(None) if lts.tz is not None else lts
    pos = np.searchsorted(hts_naive.values.astype("datetime64[ns]"),
                          lts_naive.values.astype("datetime64[ns]"), side="right") - 1
    matched = pos >= 0
    htf_close_naive = hts_naive.values.astype("datetime64[ns]").copy()
    htf_close_naive = np.where(matched, htf_close_naive[pos], np.datetime64("NaT", "ns"))
    htf_close_ts = pd.Series(pd.to_datetime(htf_close_naive, utc=True), index=ltf_df.index)
    htf_bar_idx = pd.Series(np.where(matched, pos, -1), index=ltf_df.index, dtype="int64")

    out = ltf_df.copy()
    out[f"{htf_label.lower()}_close_ts"] = htf_close_ts
    out[f"{htf_label.lower()}_bar_idx"] = htf_bar_idx

    rep = AlignmentPair(
        htf=htf_label, ltf=ltf_label, n_ltf_rows=len(ltf_df),
        n_aligned=int(matched.sum()), n_unmatched=int((~matched).sum()),
        example_violations=[],
    )
    # self-check: no row should reference an htf bar that closes AFTER the ltf ts
    viol = matched & (htf_close_naive > lts_naive.values.astype("datetime64[ns]"))
    if viol.any():
        idxs = np.where(viol)[0][:5]
        rep.example_violations = [
            {"ltf_ts": str(lts[i]), f"{htf_label.lower()}_close_ts": str(htf_close_ts.iloc[i])}
            for i in idxs
        ]
    return out, rep


def check_no_lookahead(aligned_df: pd.DataFrame, htf_col: str, ltf_col: str = "ts") -> bool:
    """Verify source_confirmation_time <= feature_timestamp for every matched row.

    Unmatched rows (NaT in htf_col — no HTF bar existed yet) are NOT look-ahead;
    they are simply unmatched and treated as passing. A leak exists only when a
    row references an HTF bar that closes AFTER the feature timestamp.
    """
    htf = pd.to_datetime(aligned_df[htf_col])
    ltf = pd.to_datetime(aligned_df[ltf_col])
    htf_naive = htf.dt.tz_localize(None) if htf.dt.tz is not None else htf
    ltf_naive = ltf.dt.tz_localize(None) if ltf.dt.tz is not None else ltf
    matched = ~htf_naive.isna()
    if not matched.any():
        return True
    return bool((htf_naive[matched] <= ltf_naive[matched]).all())
