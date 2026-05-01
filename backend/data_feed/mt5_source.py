import MetaTrader5 as mt5
import pandas as pd
import logging
import json
import os
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MT5DataSource")

class MT5DataSource:
    """
    Institutional MT5 Data Sourcing Component.
    Handles multi-timeframe (H1, M15, M5) synchronization and persistence.
    Designed for SMC hierarchical analysis: H1 Bias -> M15 Context -> M5 Execution.
    """
    
    TIMEFRAME_MAP = {
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }

    def __init__(self, config_path: str = "config/trading_params_lite.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.data_dir = Path("data_feed/storage")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Connection params from config
        dp_cfg = self.config.get("pipeline", {}).get("data_provider", {}).get("config", {})
        self.login = dp_cfg.get("login")
        self.password = dp_cfg.get("password")
        self.server = dp_cfg.get("server")
        self.symbol = self.config.get("trading", {}).get("symbol", "XAUUSD")

    def _load_config(self):
        if not self.config_path.exists():
            logger.warning(f"Config file {self.config_path} not found. Using defaults.")
            return {}
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def connect(self) -> bool:
        """Establishes connection to the MT5 Terminal."""
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            logger.error(f"MT5 Initialization failed: {mt5.last_error()}")
            return False
        logger.info("MT5 Terminal Connected Successfully.")
        return True

    def sync_timeframes(self, timeframes: list = None, count: int = 1000):
        """
        Synchronizes specified timeframes and saves to local storage.
        Ensures all layers in the SMC pipeline have sufficient historical context.
        """
        if timeframes is None:
            timeframes = ["H1", "M15", "M5"]

        sync_results = {}
        for tf in timeframes:
            mt5_tf = self.TIMEFRAME_MAP.get(tf)
            if mt5_tf is None:
                logger.warning(f"Timeframe {tf} not supported by MT5 mapping.")
                continue

            logger.info(f"Syncing {tf} bars for {self.symbol} (Count: {count})...")
            rates = mt5.copy_rates_from_pos(self.symbol, mt5_tf, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to fetch {tf} data for {self.symbol}: {mt5.last_error()}")
                continue

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Standardization for the SMC Engine
            df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            
            # Persistence for backtesting and offline analysis
            file_path = self.data_dir / f"{self.symbol}_{tf}.csv"
            df.to_csv(file_path, index=False)
            logger.info(f"Success: {len(df)} bars of {tf} saved to {file_path}")
            
            sync_results[tf] = df
            
        return sync_results

    def verify_full_sync(self):
        """Checks if all required TFs for SMC are present and synchronized."""
        required = ["H1", "M15", "M5"]
        all_ok = True
        for tf in required:
            path = self.data_dir / f"{self.symbol}_{tf}.csv"
            if not path.exists():
                logger.error(f"MISSING DATA: {tf} context for {self.symbol}")
                all_ok = False
            else:
                mtime = os.path.getmtime(path)
                logger.info(f"Verified {tf}: Last updated {datetime.fromtimestamp(mtime)}")
        return all_ok

    def shutdown(self):
        mt5.shutdown()
        logger.info("MT5 Connection Closed.")

if __name__ == "__main__":
    # Stand-alone Sync Execution
    source = MT5DataSource()
    if source.connect():
        # Sync the core SMC trilogy: H1 (Bias), M15 (Context), M5 (Trigger)
        source.sync_timeframes(["H1", "M15", "M5"], count=1000)
        source.verify_full_sync()
        source.shutdown()
    else:
        print("\n[CRITICAL] Could not connect to MT5 Terminal. Ensure the platform is running and login details are correct in config/trading_params_lite.json.")
