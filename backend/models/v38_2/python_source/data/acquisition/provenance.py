"""Provenance records for V38.2 external data acquisition.

Writes:
  backend/v38/v38_2/data/acquisition/PRICE_SOURCE.md
  backend/v38/v38_2/data/acquisition/CALENDAR_SOURCE.md
  backend/v38/v38_2/data/acquisition/DATA_PROVENANCE.md
  backend/v38/v38_2/data/acquisition/ACQUISITION_MANIFEST.json

Every record captures provider, source URL/API, retrieval timestamp, source
timeframe/instrument, coverage, row count, transformations, discarded rows +
reasons, and hashes/checksums. No silent cleaning.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ACQ_DIR = Path(__file__).resolve().parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_price_source_md(provider: str, base_url: str, instrument: str,
                          source_tf: str, derived_tfs: list,
                          retrieval_time: str, feed_status: str,
                          coverage: dict, row_counts: dict,
                          transformations: list, discards: list,
                          hashes: dict, path: Optional[Path] = None) -> Path:
    p = path or (ACQ_DIR / "PRICE_SOURCE.md")
    lines = [
        "# V38.2 — Price Data Source Provenance", "",
        f"- **provider**: {provider}",
        f"- **source URL/API**: {base_url}",
        f"- **retrieval timestamp (UTC)**: {retrieval_time}",
        f"- **source instrument**: {instrument}",
        f"- **source timeframe**: {source_tf}",
        f"- **derived timeframes**: {', '.join(derived_tfs)}",
        f"- **feed reachability**: {feed_status}",
        "",
        "## Coverage",
    ]
    for k, v in coverage.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Row counts"]
    for k, v in row_counts.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Transformations (deterministic, no fabrication)"]
    for t in transformations:
        lines.append(f"- {t}")
    lines += ["", "## Discarded records (logged, not silently cleaned)"]
    for d in discards:
        lines.append(f"- {d}")
    lines += ["", "## Hashes / checksums (SHA-256)"]
    for k, v in hashes.items():
        lines.append(f"- {k}: {v}")
    lines += ["",
              "## Feed-identity rule",
              "The existing H1/H4 data are broker/MetaQuotes-derived XAUUSDm. "
              "Dukascopy is a different feed. The two are NOT merged. Dukascopy "
              "M5/M15 are used as the research feed; the existing broker dataset "
              "remains unchanged. Cross-feed differences are reported by cross_feed.py."]
    p.write_text("\n".join(lines))
    return p


def write_calendar_source_md(status: dict, path: Optional[Path] = None) -> Path:
    p = path or (ACQ_DIR / "CALENDAR_SOURCE.md")
    lines = ["# V38.2 — Economic Calendar Source Provenance", ""]
    for k, v in status.items():
        if isinstance(v, list):
            lines.append(f"- **{k}**:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- **{k}**: {v}")
    lines += ["",
              "## Point-in-time integrity requirement",
              "Historical actual/forecast/previous must reflect what was known at "
              "the event time. Revisions are preserved via revised_previous. Values "
              "are never inferred or fabricated. Missing = missing."]
    p.write_text("\n".join(lines))
    return p


def write_data_provenance_md(price_md: Path, cal_md: Path,
                             overall_status: str, path: Optional[Path] = None) -> Path:
    p = path or (ACQ_DIR / "DATA_PROVENANCE.md")
    p.write_text("\n".join([
        "# V38.2 — Data Provenance", "",
        f"Generated (UTC): {_now()}", "",
        f"## Overall acquisition status: **{overall_status}**", "",
        "Price-data provenance: see [PRICE_SOURCE.md](PRICE_SOURCE.md)", "",
        "Calendar provenance: see [CALENDAR_SOURCE.md](CALENDAR_SOURCE.md)", "",
        "## Non-fabrication guarantee",
        "No bars, ticks, spreads, calendar events, actuals, forecasts, or previous "
        "values were fabricated, interpolated, resampled-downward, duplicated, or "
        "synthesized. Where a source was unreachable, the dataset is ABSENT and the "
        "readiness gate remains BLOCKED.",
    ]))
    return p


def write_acquisition_manifest(payload: dict, path: Optional[Path] = None) -> Path:
    p = path or (ACQ_DIR / "ACQUISITION_MANIFEST.json")
    payload = {**payload, "written_utc": _now()}
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p
