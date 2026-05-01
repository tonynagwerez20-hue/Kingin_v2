import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Set up logging for the downloader
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BulkDownloader")

def load_config(config_path: str = "config/trading_params_lite.json"):
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r') as f:
        return json.load(f)

def download_bars(symbol, timeframe, start_date, end_date):
    """
    Downloads historical bars from MT5 within a date range.
    """
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

    logger.info(f"Downloading {timeframe} bars for {symbol} from {start_date} to {end_date}...")
    
    # Use copy_rates_range for precision
    rates = mt5.copy_rates_range(symbol, mt5_tf, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        logger.error(f"Failed to fetch {timeframe} data: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    
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

    # Date Range: Last 180 days (approx 6 months)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    storage_dir = Path("data/backtest")
    storage_dir.mkdir(parents=True, exist_ok=True)

    timeframes = ["H4", "H1", "M15", "M5", "M1"]
    
    for tf in timeframes:
        df = download_bars(symbol, tf, start_date, end_date)
        if df is not None:
            file_path = storage_dir / f"{symbol}_{tf}_6mo.csv"
            df.to_csv(file_path, index=False)
            logger.info(f"SUCCESS: Saved {len(df)} bars to {file_path}")
        else:
            logger.warning(f"SKIPPED: Could not download {tf} data.")

    mt5.shutdown()
    logger.info("Download Complete.")

if __name__ == "__main__":
    main()
