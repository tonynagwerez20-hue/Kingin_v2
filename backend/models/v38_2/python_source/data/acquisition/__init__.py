"""V38.2 external-data acquisition engine.

Acquires genuine external XAUUSD data (Dukascopy M1 ticks -> M5/M15 aggregation)
and a USD economic calendar, with full provenance. No fabrication: if a source
is unreachable, the readiness gate stays BLOCKED and the failure is logged.

Modules:
- dukascopy.py   : resumable .bi5 M1 tick downloader (retry, hashes, per-hour files)
- bi5_parser.py  : LZ4 decompress + struct unpack of Dukascopy tick records -> M1 OHLCV
- aggregator.py  : deterministic M1 -> M5/M15/H1/H4 OHLC aggregation
- calendar.py    : economic-calendar acquisition scaffolding (point-in-time aware)
- provenance.py  : ACQUISITION_MANIFEST.json + PRICE/CALENDAR/DATA_PROVENANCE docs
- cross_feed.py  : compare Dukascopy-derived H1/H4 vs existing broker H1/H4
- pipeline.py    : orchestrates acquisition + validation + manifest update
"""
