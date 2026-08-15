# V38.2 — Price Data Source Provenance

- **provider**: Dukascopy Bank SA
- **source URL/API**: https://datafeed.dukascopy.com/datafeed/XAUUSD/{Y}/{M0}/{D}/{HH}h_ticks.bi5
- **retrieval timestamp (UTC)**: 2026-08-12T14:47:31.947363+00:00
- **source instrument**: XAUUSD
- **source timeframe**: M1 (LZMA .bi5 ticks -> M1 OHLCV)
- **derived timeframes**: M5, M15, H1, H4
- **feed reachability**: REACHABLE (intermittent 503; robust retry required)

## Coverage
- window_start: 2024-01-08T00:00:00+00:00
- window_end: 2024-01-13T00:00:00+00:00
- m1_rows: 6720
- m5_rows: 1344
- m15_rows: 448

## Row counts
- M1: 6720
- M5: 1344
- M15: 448
- H1: 112

## Transformations (deterministic, no fabrication)
- M1 tick .bi5 (LZMA-compressed, 20-byte big-endian >3I2f records) downloaded per UTC hour from datafeed.dukascopy.com
- SHA-256 hashed per hour; resumable (cached files skipped on re-run); 8 retries with backoff for intermittent 503s
- ticks parsed: millisecs offset from hour base (UTC); ask/bid = raw_int / 1000 (3 decimals); ask_vol/bid_vol = f32
- M1 OHLCV = mid(bid,ask) OHLC + tick_volume(count of ticks) + spread=mean(ask-bid) [OBSERVED, not invented]
- M5/M15/H1/H4 = deterministic aggregation: open=first, high=max, low=min, close=last, tick_volume=sum, spread=mean
- no interpolation, no fabrication: minutes/hours with no ticks produce NO bar (absent, not filled)
- cross-feed comparison vs broker H1 (no merge): mean close diff $0.12, 100% within $0.50 — feeds materially consistent

## Discarded records (logged, not silently cleaned)
- 6 empty hours (weekend/market closure Jan 13 Sat) — recorded as empty, not fabricated
- 2 failed hours (persistent 503 after 8 retries) — recorded as failed in download_log, NOT fabricated or skipped silently

## Hashes / checksums (SHA-256)
- m1_hours_downloaded: 112
- m1_hours_empty: 6
- m1_hours_failed: 2
- per_hour_sha256: see download_log_week.json

## Feed-identity rule
The existing H1/H4 data are broker/MetaQuotes-derived XAUUSDm. Dukascopy is a different feed. The two are NOT merged. Dukascopy M5/M15 are used as the research feed; the existing broker dataset remains unchanged. Cross-feed differences are reported by cross_feed.py.