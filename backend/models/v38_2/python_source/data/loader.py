"""Bar loaders for each timeframe. Each returns a normalized DataFrame + a
per-file quality summary. M5/M15 are ABSENT until genuine files are supplied.

Paths are configurable via V38.2DataConfig; defaults point to the repo's
existing H1/H4 files and expected (but currently absent) M5/M15/calendar paths.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from ...config import H1_8Y_CSV, H1_2024_CSV, H4_20Y_CSV, DATA_DIR
from .normalizer import parse_metaquotes, parse_plain_csv, detect_format
from .validator import validate_bars, ValidationReport
from .deduplicator import merge_frames, MergeReport
from .gap_analysis import analyze_gaps


@dataclass
class LoadResult:
    df: Optional[pd.DataFrame]
    status: str          # AVAILABLE | ABSENT | INVALID
    source_files: list
    source_sha256: list
    row_count: int
    validation: Optional[dict]
    merge: Optional[dict]
    gaps: Optional[dict]
    errors: list = field(default_factory=list)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_one(path: Path) -> pd.DataFrame:
    fmt = detect_format(path)
    return parse_metaquotes(path) if fmt == "metaquotes" else parse_plain_csv(path)


def load_h1() -> LoadResult:
    """H1 = merge of the 8y file + the 2024 redundant-subset file.
    The 2024 file is recognized as a 100% redundant subset (identical overlaps)."""
    files = [p for p in (H1_8Y_CSV, H1_2024_CSV) if p.exists()]
    if not files:
        return LoadResult(None, "ABSENT", [], [], 0, None, None, None, ["no H1 files"])
    frames = []
    sha = []
    for p in files:
        frames.append(_load_one(p)); sha.append(_sha256(p))
    try:
        df, mrep = merge_frames(frames)
    except Exception as e:
        return LoadResult(None, "INVALID", [str(p) for p in files], sha, 0, None, None, None, [str(e)])
    vrep = validate_bars(df)
    gaps = analyze_gaps(df, "H1")
    return LoadResult(df, "AVAILABLE", [str(p) for p in files], sha, len(df),
                      vrep.to_dict(), mrep.to_dict(), gaps)


def load_h4() -> LoadResult:
    if not H4_20Y_CSV.exists():
        return LoadResult(None, "ABSENT", [], [], 0, None, None, None, ["no H4 file"])
    df = _load_one(H4_20Y_CSV)
    sha = [_sha256(H4_20Y_CSV)]
    vrep = validate_bars(df)
    gaps = analyze_gaps(df, "H4")
    return LoadResult(df, "AVAILABLE", [str(H4_20Y_CSV)], sha, len(df),
                      vrep.to_dict(), None, gaps)


def load_m5(path: Optional[Path] = None) -> LoadResult:
    """M5 — ABSENT until a genuine file is supplied. Never resampled from H1."""
    p = Path(path) if path is not None else (DATA_DIR / "XAUUSDm_M5.csv")
    if not p.exists():
        return LoadResult(None, "ABSENT", [], [], 0, None, None, None,
                          [f"M5 file absent: {p} (not fabricated)"])
    df = _load_one(p)
    sha = [_sha256(p)]
    vrep = validate_bars(df)
    gaps = analyze_gaps(df, "M5")
    return LoadResult(df, "AVAILABLE", [str(p)], sha, len(df),
                      vrep.to_dict(), None, gaps)


def load_m15(path: Optional[Path] = None) -> LoadResult:
    """M15 — ABSENT until a genuine file is supplied."""
    p = Path(path) if path is not None else (DATA_DIR / "XAUUSDm_M15.csv")
    if not p.exists():
        return LoadResult(None, "ABSENT", [], [], 0, None, None, None,
                          [f"M15 file absent: {p} (not fabricated)"])
    df = _load_one(p)
    sha = [_sha256(p)]
    vrep = validate_bars(df)
    gaps = analyze_gaps(df, "M15")
    return LoadResult(df, "AVAILABLE", [str(p)], sha, len(df),
                      vrep.to_dict(), None, gaps)
