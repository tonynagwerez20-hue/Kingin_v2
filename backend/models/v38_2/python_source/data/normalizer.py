"""Bar normalization to a canonical UTC frame.

Parses two real formats and returns a single normalized DataFrame with columns
['ts','open','high','low','close','tick_volume','spread'] (schema.BAR_COLUMNS),
UTC DatetimeIndex-equivalent 'ts', float64 OHLC. No synthetic bars are created.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import BAR_COLUMNS


def parse_metaquotes(path) -> pd.DataFrame:
    """MetaQuotes tab-delimited: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE>
    <TICKVOL> <VOL> <SPREAD>."""
    df = pd.read_csv(path, sep=r"\s+")
    rename = {
        "<DATE>": "date", "<TIME>": "time", "<OPEN>": "open", "<HIGH>": "high",
        "<LOW>": "low", "<CLOSE>": "close", "<TICKVOL>": "tick_volume",
        "<VOL>": "vol", "<SPREAD": "spread", "<SPREAD>": "spread",
    }
    df = df.rename(columns=rename)
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], utc=True)
    return _frame(df)


def parse_plain_csv(path) -> pd.DataFrame:
    """Plain CSV: time,open,high,low,close[,volume] — H4 file uses this."""
    df = pd.read_csv(path)
    df = df.rename(columns={"time": "ts", "volume": "tick_volume"})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    if "spread" not in df.columns:
        df["spread"] = 0.0
    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0.0
    return _frame(df)


def _frame(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "ts": df["ts"],
        "open": df["open"].astype(np.float64),
        "high": df["high"].astype(np.float64),
        "low": df["low"].astype(np.float64),
        "close": df["close"].astype(np.float64),
        "tick_volume": df.get("tick_volume", 0).astype(np.float64),
        "spread": df.get("spread", 0).astype(np.float64),
    })
    return out[BAR_COLUMNS]


def detect_format(path) -> str:
    """Sniff whether a file is MetaQuotes tab-delim or plain CSV."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline()
    if "<DATE>" in first or "<OPEN>" in first:
        return "metaquotes"
    if "," in first and "time" in first.lower():
        return "plain"
    if "\t" in first:
        return "metaquotes"
    return "plain"
