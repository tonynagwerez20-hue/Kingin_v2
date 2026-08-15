"""Deterministic OHLC bar validation.

Checks per-row and per-frame invariants:
  - high >= max(open, close)
  - low  <= min(open, close)
  - high >= low
  - positive prices
  - no NaN / inf
  - no duplicate timestamps
  - chronological ordering

No data is modified. All problems are collected into a ValidationReport so the
manifest can record exact counts. Conflicts are never silently overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd


@dataclass
class ValidationReport:
    n_rows: int = 0
    nan_count: int = 0
    inf_count: int = 0
    duplicate_ts_count: int = 0
    invalid_ohlc_count: int = 0
    non_positive_price_count: int = 0
    not_chronological: bool = False
    invalid_ohlc_examples: list = field(default_factory=list)
    spread_status: str = "unavailable"  # "observed" | "unavailable"
    ok: bool = True
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_rows": self.n_rows, "nan_count": self.nan_count,
            "inf_count": self.inf_count, "duplicate_ts_count": self.duplicate_ts_count,
            "invalid_ohlc_count": self.invalid_ohlc_count,
            "non_positive_price_count": self.non_positive_price_count,
            "not_chronological": self.not_chronological,
            "spread_status": self.spread_status,
            "ok": self.ok, "errors": self.errors,
        }


def validate_bars(df: pd.DataFrame) -> ValidationReport:
    rep = ValidationReport()
    if df is None or len(df) == 0:
        rep.ok = False
        rep.errors.append("empty frame")
        return rep
    rep.n_rows = len(df)

    # spread status: observed (numeric) vs unavailable (sentinel/absent)
    from .schema import SPREAD_UNAVAILABLE
    if "spread" in df.columns:
        s = df["spread"]
        if s.dtype.kind in "fiu":
            rep.spread_status = "observed"
        elif (s == SPREAD_UNAVAILABLE).all():
            rep.spread_status = "unavailable"
        elif s.isna().all():
            rep.spread_status = "unavailable"
        else:
            # mixed -> treat numeric presence as observed, record any unavailable
            rep.spread_status = "observed" if (s.astype(str) != SPREAD_UNAVAILABLE).any() else "unavailable"
    else:
        rep.spread_status = "unavailable"

    # NaN / inf
    num = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    rep.nan_count = int(np.isnan(num).sum())
    rep.inf_count = int(np.isinf(num).sum())

    # duplicate timestamps
    ts = df["ts"]
    rep.duplicate_ts_count = int(ts.duplicated(keep=False).sum())

    # chronological
    if not ts.is_monotonic_increasing:
        rep.not_chronological = True

    # positive prices
    o, h, l, c = (df[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close"))
    non_pos = (o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)
    rep.non_positive_price_count = int(non_pos.sum())

    # OHLC validity: high>=max(o,c), low<=min(o,c), high>=low
    bad_high = h < np.maximum(o, c)
    bad_low = l > np.minimum(o, c)
    bad_hl = h < l
    invalid = bad_high | bad_low | bad_hl | np.isnan(num).any(axis=1) | np.isinf(num).any(axis=1) | non_pos
    rep.invalid_ohlc_count = int(invalid.sum())
    if rep.invalid_ohlc_count:
        idxs = np.where(invalid)[0][:5]
        rep.invalid_ohlc_examples = [
            {"index": int(i), "open": float(o[i]), "high": float(h[i]),
             "low": float(l[i]), "close": float(c[i])} for i in idxs
        ]

    rep.ok = (rep.nan_count == 0 and rep.inf_count == 0 and
              rep.duplicate_ts_count == 0 and rep.invalid_ohlc_count == 0 and
              rep.non_positive_price_count == 0 and not rep.not_chronological)
    return rep


def validate_calendar(df: pd.DataFrame, required_cols: list) -> dict:
    """Calendar-specific validation. Missing actual/forecast are flagged but
    NOT fabricated — recorded as missingness, never substituted."""
    if df is None or len(df) == 0:
        return {"ok": False, "n_rows": 0, "errors": ["empty calendar"], "missingness": {}}
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        return {"ok": False, "n_rows": len(df), "errors": [f"missing columns: {missing_cols}"],
                "missingness": {}}
    missingness = {c: int(df[c].isna().sum()) for c in required_cols}
    dup_ts = int(df.duplicated(subset=["ts", "event_name"]).sum())
    errors = []
    if dup_ts:
        errors.append(f"{dup_ts} duplicate (ts,event_name) rows")
    return {"ok": len(errors) == 0, "n_rows": len(df), "errors": errors,
            "missingness": missingness, "duplicate_count": dup_ts}
