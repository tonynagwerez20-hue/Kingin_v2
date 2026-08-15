# V38.2 — Economic Calendar Source Provenance

- **source**: (no accessible point-in-time source — paid API required)
- **accessible**: False
- **point_in_time**: unavailable
- **retrieval_time_utc**: 2026-08-12T14:50:09.691189+00:00
- **coverage_start**: None
- **coverage_end**: None
- **event_count**: 0
- **usd_event_count**: 0
- **actual_completeness**: 0.0
- **forecast_completeness**: 0.0
- **previous_completeness**: 0.0
- **revision_coverage**: 0.0
- **limitations**:
  - No free public point-in-time historical USD economic calendar source is accessible from this environment without paid API credentials (Trading Economics / Forex Factory historical export / FRED ALFRED).
  - Events were NOT fabricated. actual/forecast/previous were NOT inferred.
  - To supply: place a genuine calendar at backend/data/economic_calendar.csv matching the V38.2 schema (see v38/macro/engine.py:CALENDAR_COLUMNS).
- **error**: 

## Point-in-time integrity requirement
Historical actual/forecast/previous must reflect what was known at the event time. Revisions are preserved via revised_previous. Values are never inferred or fabricated. Missing = missing.