import MetaTrader5 as mt5
import pandas as pd
import json
from pathlib import Path

def test_mt5_no_login():
    print(f"--- MT5 Initialize-Only Diagnostic ---")
    # Initialize without parameters uses the active terminal session
    if not mt5.initialize():
        print(f"[FAIL] MT5 Initialize failed: {mt5.last_error()}")
        return

    acc_info = mt5.account_info()
    if acc_info:
        print(f"[OK] Already logged in to Account: {acc_info.login}")
    else:
        print(f"[FAIL] No active account session found.")
        return
    
    symbol = "XAUUSD"
    for s in [symbol, "XAUUSD.m", "GOLD", "XAUUSD.r"]:
        print(f"Testing symbol: {s}")
        if not mt5.symbol_select(s, True):
            continue
        
        rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 10)
        if rates is not None and len(rates) > 0:
            print(f"  [SUCCESS] Found {len(rates)} H1 candles for {s}!")
            return

    mt5.shutdown()

if __name__ == "__main__":
    test_mt5_no_login()
