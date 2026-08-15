"""Duplicate / overlap protection for merging bar files.

Deterministic merge with conflict detection:
  - identify overlapping timestamps
  - verify identical OHLC where overlap exists
  - reject conflicting duplicates (raise, never silent overwrite)
  - retain one canonical record per timestamp
  - log every conflict

The H1 redundant subset file is recognized here: its 12,828 timestamps are a
100% subset of the 8-year file and must NOT be counted as new observations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd


@dataclass
class MergeReport:
    n_before: int = 0
    n_after: int = 0
    overlap_timestamps: int = 0
    identical_overlaps: int = 0
    conflicting_overlaps: int = 0
    conflicts: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def merge_frames(frames: List[pd.DataFrame],
                 on_conflict: str = "keep_last_logged") -> tuple[pd.DataFrame, MergeReport]:
    """Merge bar frames deterministically.

    on_conflict:
      "raise"        — abort on any conflicting duplicate (strictest).
      "keep_last_logged" — keep the last-seen value (frames are processed in
                       order, so a later/more-recent export wins for a stale
                       partial bar) and log every conflict. NOT silent: every
                       conflict is recorded in the report and surfaced in the
                       manifest. This is the default for the H1 redundant subset,
                       where the 8y file's final bar is a stale partial and the
                       2024 export holds the corrected final bar.

    Identical overlaps are de-duplicated (one canonical record kept). The H1
    2024 file is a 100% redundant subset and is NOT counted as new data.
    """
    rep = MergeReport()
    if not frames:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close",
                                      "tick_volume", "spread"]), rep
    rep.n_before = sum(len(f) for f in frames)
    seen = {}  # ts -> row dict (canonical)
    for f in frames:
        for row in f.itertuples(index=False):
            ts = row.ts
            rec = {"ts": ts, "open": row.open, "high": row.high, "low": row.low,
                   "close": row.close, "tick_volume": row.tick_volume,
                   "spread": row.spread}
            if ts in seen:
                rep.overlap_timestamps += 1
                prev = seen[ts]
                same = all(np.isclose(prev[k], rec[k], equal_nan=False)
                           for k in ("open", "high", "low", "close"))
                if same:
                    rep.identical_overlaps += 1
                else:
                    rep.conflicting_overlaps += 1
                    rep.conflicts.append({
                        "ts": str(ts),
                        "first": {k: float(prev[k]) for k in ("open","high","low","close")},
                        "second": {k: float(rec[k]) for k in ("open","high","low","close")},
                    })
                    if on_conflict == "raise":
                        raise ConflictError(
                            f"{rep.conflicting_overlaps} conflicting duplicate timestamps; merge aborted.",
                            rep.conflicts)
                    # keep_last_logged: last-seen wins, conflict is recorded
                    seen[ts] = rec
            else:
                seen[ts] = rec
    out = pd.DataFrame(list(seen.values())).sort_values("ts").reset_index(drop=True)
    rep.n_after = len(out)
    return out, rep


class ConflictError(Exception):
    def __init__(self, msg, conflicts):
        super().__init__(msg)
        self.conflicts = conflicts
