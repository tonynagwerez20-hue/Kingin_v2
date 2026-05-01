"""
SystemBootstrapper: Handles all startup, pre-flight checks, and warmup logic.

This module extracts the initialization and validation logic from main_loop.py
to improve maintainability and separation of concerns.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
import aiohttp
import subprocess

try:
    import pkg_resources
except ImportError:
    pkg_resources = None


class SystemBootstrapper:
    """
    Handles system initialization, pre-flight checks, and warmup.
    
    Responsibilities:
    - Dependency verification
    - MT5 Bridge connection validation
    - Risk management initialization
    - Strategy initialization
    - Buffer warmup and data sync
    """
    
    def __init__(self, project_root: Path, backtest_mode: bool = False):
        """
        Initialize the bootstrapper.
        
        Args:
            project_root: Path to project root directory
            backtest_mode: Whether running in backtest/replay mode
        """
        self.project_root = project_root
        self.backtest_mode = backtest_mode
        self.bridge = None
        self.position_tracker = None
        self.risk_manager = None
        self.cro_rules = None
        self.regime_layer = None
        self.broker_watchdog = None
        self.audit_logger = None
        self.strategy_manager = None
        self.filtration = None
        self.account_balance = None
        
    def check_dependencies(self) -> None:
        """Verify all requirements are installed, attempt auto-fix if missing."""
        requirements_file = self.project_root / "requirements.txt"
        if not pkg_resources or not requirements_file.exists():
            return
        
        with open(requirements_file, "r") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        missing = []
        for req in requirements:
            try:
                pkg_resources.require(req)
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
                missing.append(req)
        
        if missing:
            print(f"[Startup] Missing dependencies detected: {missing}")
            print("[Startup] Attempting automatic installation...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
                print("[Startup] Installation successful. Please restart the system.")
                sys.exit(0)
            except Exception as e:
                print(f"[Startup] Automatic installation failed: {e}")
                print("[Startup] Please run: pip install -r requirements.txt manually.")
                sys.exit(1)
    
    def initialize_bridge(self) -> None:
        """Initialize and validate MT5 Bridge connection."""
        from execution.bridge import Bridge
        
        print(f"[Pre-Flight] Testing MT5 Bridge connection... (Backtest: {self.backtest_mode})")
        
        try:
            if self.backtest_mode:
                # Use alternative ports to avoid conflict with running system
                self.bridge = Bridge(pub_port=5565, req_port=5567)
            else:
                self.bridge = Bridge(pub_port=5555, req_port=5557)
            
            if not self.backtest_mode:
                if not self.bridge.connected:
                    print("\n[ERROR] [CRITICAL] MT5 Bridge NOT CONNECTED")
                    print("   Possible causes:")
                    print("   1. MetaTrader 5 is not running")
                    print("   2. Algo Trading is disabled (must be GREEN)")
                    print("   3. EA is not attached to chart")
                    print("   4. DLL imports not allowed in MT5 settings")
                    print("\n   Fix: Run diagnostic script first:")
                    print("   python tests/diag_system_health.py\n")
                    sys.exit(1)
                
                # Test heartbeat
                heartbeat = self.bridge.check_connection()
                if not heartbeat:
                    print("\n[ERROR] [CRITICAL] MT5 Bridge heartbeat FAILED")
                    print("   EA is not responding. Check MT5 'Experts' tab for errors.")
                    print("   Ensure EA shows smiley face (not sad face)\n")
                    sys.exit(1)
                
                print("[OK] [Pre-Flight] MT5 Bridge: CONNECTED")
            else:
                print("[OK] [Pre-Flight] MT5 Bridge: OFFLINE (Backtest Mode Active)")
                
        except Exception as e:
            print(f"\n[X] [CRITICAL] MT5 Bridge initialization failed: {e}")
            print("   Run diagnostic script: python tests/diag_system_health.py\n")
            sys.exit(1)
    
    def initialize_risk_and_strategies(self, default_balance: float) -> None:
        """Initialize risk management and strategy components."""
        from Engine.position_tracker import PositionTracker
        from support.risk.risk_manager import RiskManager
        from support.risk.cro_rules import CRORules
        from support.risk.regime_layer import RegimeLayer
        from support.risk.broker_watchdog import BrokerWatchdog
        from support.risk.audit_logger import AuditLogger
        from support.strategies.manager import StrategyManager
        from support.strategies.filter_one import FilterOne
        from support.strategies.filter_two import FilterTwo
        from support.strategies.candlestick_trigger import CandlestickStrategy
        from Engine.igof.stack import FiltrationController
        from Engine.igof.v1_engine import V1FiltrationEngine
        
        # Initialize Position Tracker
        self.position_tracker = PositionTracker()
        
        # Initialize Risk Defense
        self.risk_manager = RiskManager()
        self.cro_rules = CRORules()
        self.regime_layer = RegimeLayer()
        self.broker_watchdog = BrokerWatchdog()
        self.audit_logger = AuditLogger()
        
        # Initialize Modular Strategies (Plug-and-Play)
        alpha_strategies = [
            CandlestickStrategy(),
            FilterOne(),
            FilterTwo()
        ]
        self.strategy_manager = StrategyManager(alpha_strategies)
        
        # Initialize Modular IGOF Layers (Plug-and-Play)
        # Note: V1FiltrationEngine uses default layers from config/trading_params.json 
        # if none are provided. This is where you can inject custom layers.
        # Example: custom_layers = [MyCustomLayer(), ...]
        # self.filtration = FiltrationController(v1_engine=V1FiltrationEngine(layers=custom_layers))
        
        self.filtration = FiltrationController()
        
        print("[OK] [Pre-Flight] 5-layer Risk Defense & Modular Alpha and IGOF initialized.")
        
        # Fetch initial account balance from MT5
        self.account_balance = default_balance
        
        db = self.position_tracker.db if self.position_tracker else None
        
        if self.bridge and self.bridge.connected:
            print("[Pre-Flight] Fetching MT5 account balance...")
            fetched_balance = self.bridge.get_account_balance()
            if fetched_balance is not None:
                self.account_balance = fetched_balance
                print(f"[OK] [Pre-Flight] MT5 account balance: ${self.account_balance:,.2f}")
                if db:
                    db.set_state("account_balance", self.account_balance)
                    db.set_state("balance_last_sync", time.time())
            else:
                print(f"[WARN] [Pre-Flight] MT5 balance fetch timeout, using default: ${self.account_balance:.2f}")
        else:
            print(f"[WARN] [Pre-Flight] MT5 not connected, using default balance: ${self.account_balance:.2f}")
    
    async def warmup_buffers(self, api_url: str, warmup_timeout: int = 180) -> bool:
        """
        Wait for data buffers to populate before starting signal generation.
        
        Args:
            api_url: URL of the data feed API
            warmup_timeout: Maximum seconds to wait for buffers
        
        Returns:
            True if buffers are ready, False if timeout
        """
        print("[Main] Waiting for DTC to populate buffers...")
        warmup_start = time.time()
        
        async with aiohttp.ClientSession() as session:
            while time.time() - warmup_start < warmup_timeout:
                try:
                    # Check DTC Sync Status (Hybrid Handling)
                    async with session.get(f"{api_url}/status") as status_resp:
                        if status_resp.status == 200:
                            status_data = await status_resp.json()
                            # Allow start if we have data (Hybrid Mode)
                            pass
                    
                    # Check buffer counts
                    async with session.get(f"{api_url}/ohlc") as ohlc_resp:
                        if ohlc_resp.status == 200:
                            ohlc_data = await ohlc_resp.json()
                            h1_count = len(ohlc_data.get("H1", []))
                            m15_count = len(ohlc_data.get("M15", []))
                            m5_count = len(ohlc_data.get("M5", []))
                            
                            if h1_count > 0 and m15_count > 0 and m5_count > 0:
                                print(f"[OK] [Warmup] Buffers ready: H1={h1_count}, M15={m15_count}, M5={m5_count}")
                                return True
                            else:
                                elapsed = int(time.time() - warmup_start)
                                print(f"[Warmup] Waiting for data... ({elapsed}s) H1={h1_count}, M15={m15_count}, M5={m5_count}")
                
                except Exception as e:
                    print(f"[Warmup] API check failed: {e}")
                
                await asyncio.sleep(2)
            
            print(f"[WARN] [Warmup] Timeout after {warmup_timeout}s. Proceeding with available data.")
            return False
    
    async def run_preflight(self, api_url: str, default_balance: float) -> Dict:
        """
        Execute all pre-flight checks and initialization.
        
        Args:
            api_url: URL of the data feed API
            default_balance: Default account balance if MT5 unavailable
        
        Returns:
            Dictionary containing all initialized components
        """
        print("\n" + "="*60)
        print("PRE-FLIGHT SYSTEM VALIDATION")
        print("="*60 + "\n")
        
        # Step 1: Check dependencies
        self.check_dependencies()
        
        # Step 2: Initialize MT5 Bridge
        self.initialize_bridge()
        
        # Step 3: Initialize risk and strategies
        self.initialize_risk_and_strategies(default_balance)
        
        # Step 4: Warmup buffers
        await self.warmup_buffers(api_url)
        
        # Return all components
        return {
            "bridge": self.bridge,
            "position_tracker": self.position_tracker,
            "risk_manager": self.risk_manager,
            "cro_rules": self.cro_rules,
            "regime_layer": self.regime_layer,
            "broker_watchdog": self.broker_watchdog,
            "audit_logger": self.audit_logger,
            "strategy_manager": self.strategy_manager,
            "filtration": self.filtration,
            "account_balance": self.account_balance,
            "db": self.position_tracker.db if self.position_tracker else None
        }
