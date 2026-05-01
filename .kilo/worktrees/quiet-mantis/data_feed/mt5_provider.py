import MetaTrader5 as mt5
import pandas as pd
import logging
import json
import os
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from .base_provider import BaseDataProvider

logger = logging.getLogger("MT5Provider")

# Common symbol mappings for multi-broker compatibility (Gold variants)
SYMBOL_ALTERNATIVES = {
    "XAUUSD": [
        # Try exact names first
        "XAUUSD", "XAUUSD.i", "XAUUSD.x", "XAUUSDm",
        "GOLD", "GOLD.i", "GOLD.x", "GOLDm",
        # Try with various suffixes
        "XAUUSDmicro", "GLD", "XAU", "XAUUSD_ECN",
        "XAUUSDpro", "XAUUSDv", "XAUUSD#", "XAUUSD_",
        "Gold", "XAU_USD", "XAU/USD", "GOLD_PRO",
        "Au", "AUUSD", "XAUUSD.t",
        # Exness specific
        "XAUUSD-E", "XAUUSDm.E", "GOLD.E", "GOLDm",
        # Try without suffix
        "XAUUSDm.", "XAU.", "GOLD.",
        # Add common broker variations
        "XAUUSD_i", "XAUUSD_x", "GOLD_i", "GOLD_x",
        # More alternatives
        "GOLD#", "XAU#", "XAUUSDmicro.", "GOLDmicro"
    ]
}


class MT5DataProvider(BaseDataProvider):
    """
    MT5 Implementation of the modular Data Provider.
    """
    
    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }

    def __init__(self, config: Dict):
        self.login = config.get("login")
        self.password = config.get("password")
        self.server = config.get("server")
        
        # ── ITS Runtime Credentials bridge ──────────────────────────────
        if not self.password:
            try:
                base_dir = Path(__file__).resolve().parent.parent
                rt_path = base_dir / "runtime_credentials.json"
                if rt_path.exists():
                    with open(rt_path, "r") as f:
                        rt_data = json.load(f)
                        self.password = rt_data.get("password", "")
                        # Optionally override login/server too
                        self.login = rt_data.get("login", self.login)
                        self.server = rt_data.get("server", self.server)
            except Exception as e:
                logger.warning(f"Could not load runtime_credentials.json: {e}")
        # ─────────────────────────────────────────────────────────────────
        
        self.lite_mode = config.get("lite_mode", False)
        self.config = config  # Store full config for access to utc_offset etc
        self._symbol_map = {}  # Cache for resolved symbols

    def _resolve_symbol(self, symbol: str) -> Optional[str]:
        """
        Auto-resolve symbol to available broker symbol.
        Tries alternatives if exact match not found.
        """
        # Check cache first
        if symbol in self._symbol_map:
            return self._symbol_map[symbol]
        
        # If exact symbol exists, use it
        if mt5.symbol_info(symbol):
            self._symbol_map[symbol] = symbol
            logger.info(f"[SYMBOL] Using exact match: {symbol}")
            return symbol
        
        # Try alternatives from SYMBOL_ALTERNATIVES
        alternatives = SYMBOL_ALTERNATIVES.get(symbol, [symbol])
        for alt in alternatives:
            if mt5.symbol_info(alt):
                logger.info(f"[SYMBOL] Auto-mapped {symbol} -> {alt}")
                self._symbol_map[symbol] = alt
                return alt
        
        # Try wildcard search in available symbols
        all_symbols = mt5.symbols_get()
        available_symbol_names = []
        if all_symbols:
            for s in all_symbols:
                name = s.name
                available_symbol_names.append(name)
                # Check if symbol name contains our base
                for base in alternatives:
                    if base in name or name.startswith(base.split('.')[0]):
                        logger.info(f"[SYMBOL] Auto-mapped {symbol} -> {name}")
                        self._symbol_map[symbol] = name
                        return name
        
        logger.error(f"[SYMBOL] Could not resolve {symbol} - not found in terminal. Available symbols sample: {available_symbol_names[:20]}")
        return None

    def connect(self) -> bool:
        # Strict parameterized initialization (using config credentials ONLY)
        if not self.login:
            logger.error("No MT5 login provided in configuration. Strict login required.")
            return False

        logger.info(f"Attempting strict login to account {self.login} on {self.server}...")
        
        # 1. Initialize terminal first (shared session)
        if not mt5.initialize():
            logger.error(f"MT5 Terminal initialization failed: {mt5.last_error()}")
            return False
            
        # 2. Explicitly log in to ensure account switch
        login_res = mt5.login(login=int(self.login), password=self.password, server=self.server)
        
        if login_res:
            acc_info = mt5.account_info()
            if acc_info:
                # CRITICAL: Validate account matches config
                actual_login = acc_info.login
                if actual_login != int(self.login):
                    logger.error(f"ACCOUNT MISMATCH! Config: {self.login}, Actual: {actual_login}")
                    logger.error("SYSTEM WILL NOT TRADE - Wrong account detected!")
                    mt5.shutdown()
                    return False
                
                logger.info(f"[ACCOUNT VALIDATED] Account: {acc_info.login}, Server: {acc_info.server}, Balance: ${acc_info.balance:.2f}")
                logger.info(f"[BROKER TIME] UTC Offset configured: {self.config.get('utc_offset', 'Not set')}")
                
                # Log available symbols for debugging
                all_symbols = mt5.symbols_get()
                if all_symbols:
                    symbol_names = [s.name for s in all_symbols][:20]  # First 20
                    logger.info(f"[SYMBOLS] Available (sample): {symbol_names}...")
                
                return True
            else:
                logger.error("MT5 account_info() returned None after successful login.")
                return False
        else:
            logger.error(f"MT5 Login failed for account {self.login}: {mt5.last_error()}")
            return False

    def is_connected(self) -> bool:
        ti = mt5.terminal_info()
        return ti.connected if ti else False

    def get_latest_candles(self, symbol: str, timeframe: str, count: int) -> list:
        mt5_tf = self.TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M5)
        
        # Auto-resolve symbol
        resolved_symbol = self._resolve_symbol(symbol)
        if not resolved_symbol:
            logger.error(f"Symbol {symbol} could not be resolved.")
            return []
        
        # Ensure symbol is selected and synced
        symbol_info = mt5.symbol_info(resolved_symbol)
        if symbol_info is None:
            logger.error(f"Symbol {resolved_symbol} not found in terminal.")
            return []
            
        if not symbol_info.visible:
            if not mt5.symbol_select(resolved_symbol, True):
                logger.error(f"Failed to select symbol {resolved_symbol}: {mt5.last_error()}")
                return []
        
        rates = mt5.copy_rates_from_pos(resolved_symbol, mt5_tf, 0, count)
        if rates is None or len(rates) == 0:
            err = mt5.last_error()
            logger.warning(f"No history found for {symbol} on {timeframe}. MT5 Error: {err}")
            return []

        df = pd.DataFrame(rates)
        # Keep time as unix integer for JSON serialization
        df['time'] = df['time'].astype(int)
        
        # Standardize for the pipeline
        return df.to_dict('records')

    def get_live_ticks(self, symbol: str) -> pd.DataFrame:
        """
        Fetch latest 10 ticks and convert to 'mini-candles' for stitching.
        """
        # Auto-resolve symbol
        resolved_symbol = self._resolve_symbol(symbol)
        if not resolved_symbol:
            return pd.DataFrame()
            
        ticks = mt5.copy_ticks_from(resolved_symbol, datetime.now(), 10, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            return pd.DataFrame()
            
        df = pd.DataFrame(ticks)
        # Note: In a real-world scenario, we'd aggregate these ticks 
        return df

    def get_tick_data(self, symbol: str) -> Dict:
        """
        Fetch the absolute latest tick (bid/ask).
        """
        # Auto-resolve symbol
        resolved_symbol = self._resolve_symbol(symbol)
        if not resolved_symbol:
            return {"bid": 0.0, "ask": 0.0, "time": datetime.now().timestamp()}
            
        tick = mt5.symbol_info_tick(resolved_symbol)
        if tick is None:
            return {"bid": 0.0, "ask": 0.0, "time": datetime.now().timestamp()}
            
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "time": tick.time
        }

    def get_account_info(self) -> Dict:
        """
        Fetch current account balance and equity.
        """
        acc = mt5.account_info()
        if acc is None:
            logger.warning("MT5 account_info() returned None. Check terminal connection.")
            return {"balance": 0.0, "equity": 0.0}
        
        return {
            "balance": acc.balance,
            "equity": acc.equity,
            "login": acc.login,
            "server": acc.server
        }

    def shutdown(self):
        mt5.shutdown()
