"""Multi-timeframe OHLC bar loading and normalization for V38.

Reads the real XAUUSD CSV files shipped with the repository. Combines the two
overlapping H1 files into one de-duplicated, time-sorted series. Provides a
deterministic @dataclass Bar and a DataFrame with a proper UTC DatetimeIndex.

No synthetic bars are ever generated here — only real OHLC is returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import H1_2024_CSV, H1_8Y_CSV, H4_20Y_CSV, V38Config


@dataclass(frozen=True)
class Bar:
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return self.close - self.open


def _parse_mt_tabular(path, tf_label: str) -> pd.DataFrame:
    """Parse MetaQuotes-style tab-delimited OHLC (DATE/TIME/OPEN/...)."""
    df = pd.read_csv(path, sep=r"\s+")
    df = df.rename(columns={
        "<DATE>": "date", "<TIME>": "time", "<OPEN>": "open",
        "<HIGH>": "high", "<LOW>": "low", "<CLOSE>": "close",
        "<TICKVOL>": "volume", "<VOL>": "vol", "<SPREAD>": "spread",
    })
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], utc=True)
    out = pd.DataFrame({
        "ts": df["ts"],
        "open": df["open"].astype(np.float64),
        "high": df["high"].astype(np.float64),
        "low": df["low"].astype(np.float64),
        "close": df["close"].astype(np.float64),
        "volume": df.get("volume", 0).astype(np.float64),
        "spread": df.get("spread", 0).astype(np.float64),
    })
    out = out.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
    return out


def _parse_h4_csv(path: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["time"], utc=True)
    out = pd.DataFrame({
        "ts": df["ts"],
        "open": df["open"].astype(np.float64),
        "high": df["high"].astype(np.float64),
        "low": df["low"].astype(np.float64),
        "close": df["close"].astype(np.float64),
        "volume": df["volume"].astype(np.float64),
        "spread": 0.0,
    })
    return out.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)


def load_h1() -> pd.DataFrame:
    """Load the merged, de-duplicated XAUUSD H1 series (8y + 2024 file)."""
    frames = []
    if H1_8Y_CSV.exists():
        frames.append(_parse_mt_tabular(H1_8Y_CSV, "H1"))
    if H1_2024_CSV.exists():
        frames.append(_parse_mt_tabular(H1_2024_CSV, "H1"))
    if not frames:
        raise FileNotFoundError(f"No H1 CSVs found under {H1_8Y_CSV.parent}")
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
    return df


def load_h4() -> pd.DataFrame:
    if not H4_20Y_CSV.exists():
        raise FileNotFoundError(H4_20Y_CSV)
    return _parse_h4_csv(H4_20Y_CSV)


def resample_to(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate an H1/H4 frame to a higher rule (e.g. '4H','1D','1W').

    Real lower->higher aggregation only; never synthesizes finer bars.
    """
    d = df.set_index("ts")
    agg = d.resample(rule).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        spread=("spread", "mean"),
    ).dropna(subset=["open", "high", "low", "close"]).reset_index()
    return agg


def atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Wilder-style ATR aligned to df rows (length == len(df))."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    prev_close = np.empty(n)
    prev_close[0] = c[0]
    prev_close[1:] = c[:-1]
    tr = np.maximum.reduce([
        h - l,
        np.abs(h - prev_close),
        np.abs(l - prev_close),
    ])
    # Wilder smoothing (RMA / exponential moving average of TR).
    alpha = 1.0 / period
    atr_arr = np.full(n, np.nan)
    if n >= period:
        atr_arr[period - 1] = tr[:period].mean()
        for i in range(period, n):
            atr_arr[i] = atr_arr[i - 1] * (1 - alpha) + tr[i] * alpha
    return atr_arr


def session_of(ts: pd.Timestamp, cfg: V38Config) -> str:
    hour = ts.hour
    for name, (start, end) in cfg.session_defs.items():
        if start <= hour < end:
            return name
    return "off"


def session_index(ts: pd.Timestamp, cfg: V38Config) -> int:
    name = session_of(ts, cfg)
    return {"asian": 0, "london": 1, "overlap": 2, "ny": 3, "off": 4}[name]


def available_timeframes() -> dict:
    """Report what real data is present (drives dataset-size feasibility)."""
    return {
        "H1": {"path": str(H1_8Y_CSV), "exists": H1_8Y_CSV.exists()},
        "H1_2024": {"path": str(H1_2024_CSV), "exists": H1_2024_CSV.exists()},
        "H4": {"path": str(H4_20Y_CSV), "exists": H4_20Y_CSV.exists()},
    }
