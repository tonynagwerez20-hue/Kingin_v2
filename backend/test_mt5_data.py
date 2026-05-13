import MetaTrader5 as mt5
import pandas as pd
import json
from pathlib import Path

def test_mt5_data():
    config_path = Path("c:/Users/LENOVO/Desktop/kingin-master/backend/config/trading_params_lite.json")
    with open(config_path, "r") as f:
        cfg = json.load(f)
    
    creds = cfg.get("pipeline", {}).get("data_provider", {}).get("config", {})
    login = creds.get("login")
    password = creds.get("password")
    server = creds.get("server")
    
    print(f"--- MT5 Data Fetch Diagnostic ---")
    if not mt5.initialize():
        print(f"[FAIL] MT5 Initialize failed: {mt5.last_error()}")
        return

    if not mt5.login(int(login), password=password, server=server):
        print(f"[FAIL] MT5 Login failed: {mt5.last_error()}")
        return
    
    print(f"[OK] MT5 Logged in as {login}")
    
    symbol = "XAUUSD"
    # Try common alternatives if base fails
    for s in [symbol, "XAUUSD.m", "GOLD", "XAUUSD.r"]:
        print(f"Testing symbol: {s}")
        if not mt5.symbol_select(s, True):
            print(f"  [SKIP] Symbol {s} not found/selected.")
            continue
        
        rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, 10)
        if rates is not None and len(rates) > 0:
            print(f"  [SUCCESS] Found {len(rates)} H1 candles for {s}!")
            print(f"  Sample: {rates[0]}")
            return
        else:
            print(f"  [FAIL] No rates found for {s}. Error: {mt5.last_error()}")

    mt5.shutdown()

if __name__ == "__main__":
    test_mt5_data()
