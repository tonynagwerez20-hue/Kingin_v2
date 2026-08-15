"""Deterministic M1 -> M5/M15/H1/H4 OHLC aggregation.

Aggregation rules (no fabrication, no interpolation):
  open  = open of the first M1 bar in the window
  high  = max(high) of all M1 bars in the window
  low   = min(low) of all M1 bars in the window
  close = close of the last M1 bar in the window
  tick_volume = sum(tick_volume)
  spread = mean(spread) if all source bars have observed spread; else "UNAVAILABLE"

A higher-timeframe bar with zero source M1 bars is ABSENT (never fabricated).
Weekend/market-closure gaps are therefore naturally represented by absent bars.
"""
from __future__ import annotations

import pandas as pd

TF_MINUTES = {"M5": 5, "M15": 15, "H1": 60, "H4": 240}


def aggregate(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    if m1.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close",
                                     "tick_volume", "spread"])
    minutes = TF_MINUTES[tf]
    df = m1.copy().sort_values("ts").reset_index(drop=True)
    df["bucket"] = df["ts"].dt.floor(f"{minutes}min")
    g = df.groupby("bucket")
    out = pd.DataFrame({
        "ts": list(g.groups.keys()),
        "open": g["open"].first().to_numpy(),
        "high": g["high"].max().to_numpy(),
        "low": g["low"].min().to_numpy(),
        "close": g["close"].last().to_numpy(),
        "tick_volume": g["tick_volume"].sum().to_numpy(),
    })
    spread_mean = g["spread"].mean().to_numpy()
    out["spread"] = spread_mean
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out[["ts", "open", "high", "low", "close", "tick_volume", "spread"]]


def write_csv(df: pd.DataFrame, path):
    path = path if hasattr(path, "write") else open(path, "w")
    df.to_csv(path, index=False)
    if not hasattr(path, "write"):
        path.close()
