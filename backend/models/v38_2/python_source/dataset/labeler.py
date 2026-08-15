"""Leakage-safe barrier labeler.

Labels are generated ONLY AFTER the pre-entry snapshot is frozen. Outcome:

  TP reached first  -> label = 1
  SL reached first  -> label = 0
  neither within horizon -> censored (label = -1, barrier_reached="censored")

Simultaneous TP/SL touches (same bar high>=TP and low<=SL):
  policy = "SL_wins" (default, conservative) -> label = 0
  policy = "TP_wins" -> label = 1
  This is explicitly documented in config.label_simultaneous_policy.

The labeler uses only FUTURE bars relative to entry (entry bar exclusive), so
no feature can contain label information. MFE/MAE/time-to-resolution are also
measured strictly after entry.
"""
from __future__ import annotations

from typing import List
import numpy as np
import pandas as pd

from ..config import V38Config
from .setup_detector import CandidateSetup


def label_setup(setup: CandidateSetup, df: pd.DataFrame, cfg: V38Config
                ) -> CandidateSetup:
    """Mutates `setup` in place with label + outcome fields."""
    n = len(df)
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    b = setup.bar_index
    horizon = max(2, int(cfg.label_max_bars))
    entry = setup.entry_price
    sl = setup.sl
    tp = setup.tp
    is_long = setup.direction == "bullish"

    mfe = 0.0
    mae = 0.0
    resolved = False
    for j in range(b + 1, min(n, b + 1 + horizon)):
        h = float(highs[j])
        l = float(lows[j])
        if is_long:
            mfe = max(mfe, h - entry)
            mae = max(mae, entry - l)
            tp_hit = h >= tp
            sl_hit = l <= sl
        else:
            mfe = max(mfe, entry - l)
            mae = max(mae, h - entry)
            tp_hit = l <= tp
            sl_hit = h >= sl

        if tp_hit and sl_hit:
            if cfg.label_simultaneous_policy == "TP_wins":
                setup.label = 1
                setup.barrier_reached = "TP"
            else:
                setup.label = 0
                setup.barrier_reached = "SL"
            setup.time_to_resolution = j - b
            resolved = True
            break
        if tp_hit:
            setup.label = 1
            setup.barrier_reached = "TP"
            setup.time_to_resolution = j - b
            resolved = True
            break
        if sl_hit:
            setup.label = 0
            setup.barrier_reached = "SL"
            setup.time_to_resolution = j - b
            resolved = True
            break

    setup.mfe = float(mfe)
    setup.mae = float(mae)
    if not resolved:
        setup.label = -1  # censored
        setup.barrier_reached = "censored"
        setup.time_to_resolution = horizon
    # future_return = price at horizon vs entry (signed favourably)
    end_idx = min(n - 1, b + horizon)
    future_close = float(df["close"].to_numpy()[end_idx])
    if is_long:
        setup.future_return = float(future_close - entry)
    else:
        setup.future_return = float(entry - future_close)
    return setup
