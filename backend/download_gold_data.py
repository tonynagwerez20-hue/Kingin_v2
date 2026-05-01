"""
Download Gold (XAUUSD) 6-Month OHLC Data from MT5
=================================================

This script downloads 6 months of XAUUSD hourly data from MetaTrader 5
and saves it for use with the Gold Research Strategy backtest.

Usage:
    python download_gold_data.py

Output:
    data/XAUUSD_H1_6mo.csv - 6 months of hourly Gold data
"""

import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GoldDataDownloader")


def load_config(config_path: str = "config/trading_params_lite.json"):
    """Load MT5 configuration from settings file."""
    if not os.path.exists(config_path):
        logger.warning(f"Config not found: {config_path}, using defaults")
        return {}
    with open(config_path, 'r') as f:
        return json.load(f)


def download_gold_data(symbol="XAUUSD", timeframe="H1", n_months=6):
    """
    Download Gold OHLCV data from MT5.
    
    Args:
        symbol: Trading symbol (default: XAUUSD)
        timeframe: Timeframe (H1, H4, M15, etc.)
        n_months: Number of months of history to download
    
    Returns:
        DataFrame with OHLCV data
    """
    # Initialize MT5
    config = load_config()
    dp_cfg = config.get("pipeline", {}).get("data_provider", {}).get("config", {})
    
    if not mt5.initialize(
        login=dp_cfg.get("login"),
        password=dp_cfg.get("password"),
        server=dp_cfg.get("server")
    ):
        logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
        return None
    
    logger.info(f"MT5 initialized successfully")
    
    # Timeframe mapping
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    
    mt5_tf = tf_map.get(timeframe)
    if mt5_tf is None:
        logger.error(f"Unsupported timeframe: {timeframe}")
        mt5.shutdown()
        return None
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_months * 30)
    
    logger.info(f"Downloading {n_months} months of {symbol} {timeframe} data...")
    logger.info(f"Date range: {start_date} to {end_date}")
    
    # Download data
    rates = mt5.copy_rates_range(symbol, mt5_tf, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch data: {mt5.last_error()}")
        mt5.shutdown()
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    
    # Save to CSV
    os.makedirs("data", exist_ok=True)
    output_path = f"data/{symbol}_{timeframe}_6mo.csv"
    df.to_csv(output_path, index=False)
    
    logger.info(f"SUCCESS: Saved {len(df)} bars to {output_path}")
    logger.info(f"Date range: {df['time'].min()} to {df['time'].max()}")
    
    # Shutdown MT5
    mt5.shutdown()
    logger.info("MT5 shutdown complete")
    
    return df


def main():
    """Main entry point."""
    logger.info("=== Downloading Gold (XAUUSD) 6-Month Data ===")
    
    # Download H1 data (recommended for strategy)
    df = download_gold_data(symbol="XAUUSD", timeframe="H1", n_months=6)
    
    if df is not None:
        logger.info(f"Download complete! Data shape: {df.shape}")
        logger.info(f"Sample data:\n{df.head()}")
    else:
        logger.error("Failed to download data")


if __name__ == "__main__":
    main()
