"""Economic-calendar loader. Uses the schema fixed in v38/macro/engine.py.

ABSENT until a genuine calendar file is supplied. Missing actual/forecast are
recorded as missingness and NEVER fabricated (no actual=forecast, actual=previous,
forecast=0 substitutions).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from ...config import DATA_DIR
from .schema import CALENDAR_COLUMNS
from .validator import validate_calendar


@dataclass
class CalendarLoadResult:
    df: Optional[pd.DataFrame]
    status: str
    source_file: str
    source_sha256: str
    row_count: int
    validation: Optional[dict]
    errors: list = field(default_factory=list)


def load_calendar(path: Optional[Path] = None) -> CalendarLoadResult:
    p = Path(path) if path is not None else (DATA_DIR / "economic_calendar.csv")
    if not p.exists():
        return CalendarLoadResult(None, "ABSENT", str(p), "", 0, None,
                                  [f"calendar file absent: {p} (not fabricated)"])
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        df = pd.read_csv(p)
    except Exception as e:
        return CalendarLoadResult(None, "INVALID", str(p), sha, 0, None, [f"parse error: {e}"])
    # normalize ts to UTC
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    v = validate_calendar(df, CALENDAR_COLUMNS)
    status = "VALIDATED" if v["ok"] else "INVALID"
    return CalendarLoadResult(df, status, str(p), sha, len(df), v, v.get("errors", []))
