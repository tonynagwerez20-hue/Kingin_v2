import MetaTrader5 as mt5
import json
import os
from pathlib import Path

def verify_connection():
    config_path = Path("config/trading_params_lite.json")
    if not config_path.exists():
        print(f"Error: Config not found at {config_path}")
        return

    with open(config_path, 'r') as f:
        config = json.load(f)

    mt5_cfg = config.get("pipeline", {}).get("data_provider", {}).get("config", {})
    login = mt5_cfg.get("login")
    password = mt5_cfg.get("password")
    server = mt5_cfg.get("server")

    print(f"Attempting to connect to MT5 Server: {server} as {login}...")
    
    if not mt5.initialize(login=login, password=password, server=server):
        print(f"MT5 Initialization FAILED: {mt5.last_error()}")
        return False

    print("MT5 Initialization SUCCESSFUL")
    
    # Check account info
    acc_info = mt5.account_info()
    if acc_info:
        print(f"Account: {acc_info.login}")
        print(f"Balance: {acc_info.balance}")
        print(f"Equity: {acc_info.equity}")
        print(f"Broker: {acc_info.company}")
    else:
        print("Failed to retrieve account information.")

    # Check terminal info
    term_info = mt5.terminal_info()
    if term_info:
        print(f"Terminal: {term_info.name}")
        print(f"Connected: {term_info.connected}")

    mt5.shutdown()
    print("\nMT5 Connection verification complete.")
    return True

if __name__ == "__main__":
    verify_connection()
