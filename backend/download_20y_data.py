"""
Download 20 years of historical data from MT5 for all timeframes - CHUNKED approach.
MT5 has limits on single data requests, so we'll download in 1-year chunks.
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Download20YearsChunked")

def load_config(config_path: str = "config/trading_params_lite.json"):
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r') as f:
        return json.load(f)

def download_bars_chunked(symbol, timeframe, start_date, end_date, chunk_days=365):
    """Download historical bars from MT5 in chunks to avoid API limits."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4
    }
    
    mt5_tf = tf_map.get(timeframe)
    if mt5_tf is None:
        logger.error(f"Unsupported timeframe: {timeframe}")
        return None

    all_rates = []
    current_start = start_date
    total_bars = 0
    
    logger.info(f"Downloading {timeframe} bars (chunked) from {start_date.date()} to {end_date.date()}...")
    
    while current_start < end_date:
        chunk_end = min(current_start + timedelta(days=chunk_days), end_date)
        logger.info(f"  Downloading {timeframe} chunk: {current_start.date()} to {chunk_end.date()}")
        
        try:
            rates = mt5.copy_rates_range(symbol, mt5_tf, current_start, chunk_end)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"  No data for {timeframe} chunk: {current_start.date()} to {chunk_end.date()}")
            else:
                all_rates.extend(rates)
                total_bars += len(rates)
                logger.info(f"    Got {len(rates)} bars (total: {total_bars})")
        
        except Exception as e:
            logger.error(f"Error downloading {timeframe} chunk: {e}")
        
        current_start = chunk_end

    if not all_rates:
        logger.error(f"Failed to fetch any {timeframe} data")
        return None

    df = pd.DataFrame(all_rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].drop_duplicates()
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    df = df.sort_values('time').reset_index(drop=True)
    
    logger.info(f"Final {timeframe}: {len(df)} unique bars")
    return df

def main():
    config = load_config()
    dp_cfg = config.get("pipeline", {}).get("data_provider", {}).get("config", {})
    symbol = config.get("trading", {}).get("symbol", "XAUUSD")
    
    # MT5 Auth
    if not mt5.initialize(
        login=dp_cfg.get("login"),
        password=dp_cfg.get("password"),
        server=dp_cfg.get("server")
    ):
        logger.error(f"MT5 Auth Failed: {mt5.last_error()}")
        return

    # Date Range: Last 20 years
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*20)  # 20 years
    
    logger.info(f"=" * 80)
    logger.info(f"DOWNLOADING 20 YEARS OF DATA (CHUNKED)")
    logger.info(f"Period: {start_date.date()} to {end_date.date()}")
    logger.info(f"=" * 80)
    
    storage_dir = Path("data/backtest_20y")
    storage_dir.mkdir(parents=True, exist_ok=True)

    timeframes = ["H4", "H1", "M15", "M5"]
    
    for tf in timeframes:
        df = download_bars_chunked(symbol, tf, start_date, end_date, chunk_days=365)
        if df is not None and len(df) > 0:
            file_path = storage_dir / f"{symbol}_{tf}_20y.csv"
            df.to_csv(file_path, index=False)
            logger.info(f"✓ SUCCESS: Saved {len(df)} bars to {file_path}\n")
        else:
            logger.warning(f"✗ SKIPPED: Could not download {tf} data.\n")

    mt5.shutdown()
    logger.info("=" * 80)
    logger.info("20-Year Download Complete.")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
