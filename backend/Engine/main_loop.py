import asyncio
import sys
from pathlib import Path
import pandas as pd
import time
import importlib.util
import gc
import subprocess
try:
    import pkg_resources
except ImportError:
    pkg_resources = None
import argparse
import aiohttp


# ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# --- CONFIG ---
from config.settings import (
    API_URL, DEFAULT_ACCOUNT_BALANCE, PIP_VALUE, PIP_SIZE, 
    BALANCE_REFRESH_INTERVAL, LOOP_INTERVAL, ENABLE_CLEANUP, ENABLE_IGOF
)


# --- Imports ---
# Dynamic import for dispatcher
try:
    from networking.dispatcher import DataDispatcher, delta_buffers, ohlc_buffers, dispatch_batch
    from networking.server import build_delta_struct
except ImportError:
    # Check if we need to look in networking if the root import fails
    networking_path = project_root / "networking"
    sys.path.append(str(networking_path))
    # Try data_feed path as well since we know it's there
    data_feed_path = project_root / "data_feed" 
    sys.path.append(str(data_feed_path))
    
    try:
        from data_feed.dispatcher import DataDispatcher, delta_buffers, ohlc_buffers, dispatch_batch
    except ImportError:
         from dispatcher import DataDispatcher, delta_buffers, ohlc_buffers, dispatch_batch

    from server import build_delta_struct

# Define Buffer Aliases
HTF_BUFFER = ohlc_buffers["H1"]
MTF_BUFFER = ohlc_buffers["M15"]
LTF_BUFFER = ohlc_buffers["M5"]

# Logic imports
try:
    from support.strategies.composite_strategy import CompositeStrategy
    from support.strategies.manager import StrategyManager
    from support.strategies.orderflow import OrderflowStrategy
    from support.strategies.filter_one import FilterOne
    from support.strategies.filter_two import FilterTwo
    
    from support.risk.risk_manager import RiskManager
    from support.risk.cro_rules import CRORules
    from support.risk.regime_layer import RegimeLayer
    from support.risk.broker_watchdog import BrokerWatchdog
    
    from support.audit_logger import AuditLogger
    
    from execution.bridge import Bridge
    from Engine.position_tracker import PositionTracker
    from support.notifications.alert_manager import alert_manager
    # IGOF Filtration
    from Engine.igof.stack import FiltrationController
except ImportError as e:
    print(f"[CRITICAL] Import Error in engine logic modules: {e}")
    print("[CRITICAL] Engine cannot start. Run: pip install -r requirements.txt")
    sys.exit(1)


# --- LOGGING SETUP ---
class LoggerWriter:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def isatty(self):
        return False

    def fileno(self):
        return self.log.fileno()

# Redirect stdout/stderr to file + console
log_dir = project_root / "storage" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
sys.stdout = LoggerWriter(log_dir / "engine_live.log")
sys.stderr = sys.stdout


async def main():
    # Parse CLI Arguments
    parser = argparse.ArgumentParser(description="Hedge Gold Trading Engine")
    parser.add_argument("--backtest", action="store_true", help="Run in Backtest/Replay mode (records signals to CSV, skips MT5 execution)")
    args = parser.parse_args()
    
    backtest_mode = args.backtest
    if backtest_mode:
        print("\n" + "!"*60)
        print("!!! RUNNING IN BACKTEST / REPLAY MODE !!!")
        print("!!! Signals will be recorded to data/backtest_signals.csv !!!")
        print("!"*60 + "\n")

    # ========== SYSTEM BOOTSTRAP ==========
    from Engine.system_bootstrapper import SystemBootstrapper
    
    bootstrapper = SystemBootstrapper(project_root, backtest_mode)
    components = await bootstrapper.run_preflight(API_URL, DEFAULT_ACCOUNT_BALANCE)
    
    # Extract components
    bridge = components["bridge"]
    position_tracker = components["position_tracker"]
    risk_manager = components["risk_manager"]
    cro_rules = components["cro_rules"]
    regime_layer = components["regime_layer"]
    broker_watchdog = components["broker_watchdog"]
    audit_logger = components["audit_logger"]
    strategy_manager = components["strategy_manager"]
    filtration = components["filtration"]
    account_balance = components["account_balance"]
    db = components["db"]
    
    last_balance_check = 0
    
    # ========== MAIN TRADING LOOP ==========
    from Engine.trading_loop_controller import TradingLoopController
    
    # Initialize trading loop controller with all dependencies
    trading_loop = TradingLoopController(
        api_url=API_URL,
        bridge=bridge,
        position_tracker=position_tracker,
        risk_manager=risk_manager,
        cro_rules=cro_rules,
        regime_layer=regime_layer,
        broker_watchdog=broker_watchdog,
        audit_logger=audit_logger,
        strategy_manager=strategy_manager,
        filtration=filtration,
        db=db,
        backtest_mode=backtest_mode
    )
    
    # Set initial account balance
    trading_loop.account_balance = account_balance
    trading_loop.loop_interval = LOOP_INTERVAL
    trading_loop.balance_refresh_interval = BALANCE_REFRESH_INTERVAL
    
    # Run the trading loop
    await trading_loop.run()


if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
