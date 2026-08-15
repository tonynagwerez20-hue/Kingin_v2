#!/usr/bin/env python3
"""V38.2 — Full jetta candle acquisition driver (2018 → latest).

Acquires genuine Dukascopy M1 source candles via the fast jetta API route.
Fetches BOTH BID and ASK to compute MID-price M1 matching the V38.2 convention.

Resumable: cached daily JSON files are skipped on restart.
This does NOT interfere with the existing .bi5 tick driver (different paths).
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from v38.v38_2.data.acquisition import jetta_candles as jc

START = datetime(2018, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 3, 4, tzinfo=timezone.utc)
MANIFEST = Path("data/raw/dukascopy/xauusd/candles_m1/manifest_full.json")


def main():
    print(f"[jetta] acquiring {START.date()} → {END.date()} (BID+ASK M1 candles)")
    t0 = time.time()
    manifest = jc.download_range(START, END, fetch_mid=True, manifest_path=MANIFEST)
    wall = time.time() - t0
    s = manifest["summary"]
    print(f"[jetta] DONE in {wall:.1f}s")
    print(f"  days: dl={s['days_downloaded']}, cached={s['days_cached']}, "
          f"empty={s['days_empty']}, failed={s['days_failed']}")
    print(f"  M1 bars (one side): {s['m1_bars_total']}")
    print(f"  download time: {s['total_download_time_s']}s")
    if s["days_failed"] > 0:
        failed_days = [d for d, v in manifest["days"].items()
                       if any(sd["status"] == "failed" for sd in v["sides"].values())]
        print(f"  FAILED days: {failed_days[:10]}{'...' if len(failed_days)>10 else ''}")


if __name__ == "__main__":
    main()
