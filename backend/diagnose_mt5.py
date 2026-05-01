"""
MT5 Diagnostic Tool
===================
Checks MT5 Terminal status, network connectivity, and connection issues.
Run this to troubleshoot "Authorization failed" errors.

Usage: python diagnose_mt5.py [account] [password] [server]
       python diagnose_mt5.py  (uses config/trading_params_lite.json)
"""

import sys
import json
import os
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    print("ERROR: MetaTrader5 not installed. Run: pip install MetaTrader5")
    sys.exit(1)


def load_config():
    """Load MT5 credentials from config file"""
    config_path = Path("config/trading_params_lite.json")
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        mt5_cfg = config.get("pipeline", {}).get("data_provider", {}).get("config", {})
        return {
            "login": mt5_cfg.get("login"),
            "password": mt5_cfg.get("password"),
            "server": mt5_cfg.get("server")
        }
    except Exception as e:
        print(f"ERROR reading config: {e}")
        return None


def diagnose():
    """Run comprehensive MT5 diagnostics"""
    
    # Get credentials
    if len(sys.argv) >= 4:
        login = int(sys.argv[1])
        password = sys.argv[2]
        server = sys.argv[3]
        print(f"Using command-line credentials")
    else:
        cfg = load_config()
        if cfg:
            login = cfg.get("login")
            password = cfg.get("password")
            server = cfg.get("server")
            print(f"Using credentials from config/trading_params_lite.json")
        else:
            print("ERROR: No credentials provided and config file not found")
            print("Usage: python diagnose_mt5.py <account> <password> <server>")
            sys.exit(1)
    
    print("\n" + "="*60)
    print("MT5 DIAGNOSTIC REPORT")
    print("="*60 + "\n")
    
    print(f"[1] Checking MT5 Terminal Status...")
    print(f"    Expected Server: {server}")
    print(f"    Expected Login: {login}\n")
    
    # Step 1: Try to initialize
    print(f"[2] Attempting MT5 initialization...")
    try:
        init_result = mt5.initialize()
        if init_result:
            print(f"    ✓ MT5 initialization SUCCESS")
        else:
            err = mt5.last_error()
            print(f"    ✗ MT5 initialization FAILED")
            print(f"      Error code: {err[0] if err else 'Unknown'}")
            print(f"      Error msg: {err[1] if err else 'Unknown'}")
            print(f"\n    DIAGNOSTIC:")
            print(f"      • Is MetaTrader5 Terminal running?")
            print(f"      • Check: Start > Programs > MetaTrader5")
            print(f"      • If not running, open it and try again")
            return
    except Exception as e:
        print(f"    ✗ Exception during initialization: {e}")
        return
    
    # Step 2: Check terminal info
    print(f"\n[3] Checking Terminal Information...")
    try:
        term_info = mt5.terminal_info()
        if term_info:
            print(f"    ✓ Terminal info retrieved:")
            print(f"      Name: {term_info.name}")
            print(f"      Company: {term_info.company}")
            print(f"      Connected: {term_info.connected}")
            if not term_info.connected:
                print(f"\n    WARNING: Terminal is NOT connected to server!")
                print(f"      • Check internet connection")
                print(f"      • Check firewall/antivirus")
                print(f"      • Try clicking 'Connect' in MT5 terminal")
        else:
            print(f"    ✗ Could not retrieve terminal info")
    except Exception as e:
        print(f"    ✗ Exception: {e}")
    
    # Step 3: Try to login
    print(f"\n[4] Attempting login with provided credentials...")
    try:
        auth_result = mt5.login(login, password=password, server=server)
        if auth_result:
            print(f"    ✓ Login SUCCESS")
            
            # Step 4: Get account info
            print(f"\n[5] Retrieving Account Information...")
            acc_info = mt5.account_info()
            if acc_info:
                print(f"    ✓ Account info retrieved:")
                print(f"      Login: {acc_info.login}")
                print(f"      Name: {acc_info.name}")
                print(f"      Broker: {acc_info.company}")
                print(f"      Server: {acc_info.server}")
                print(f"      Balance: {acc_info.balance}")
                print(f"      Equity: {acc_info.equity}")
                print(f"      Type: {'Real' if acc_info.trade_mode == 0 else 'Demo'}")
            else:
                print(f"    ✗ Could not retrieve account info")
            
            # Step 5: Check symbols
            print(f"\n[6] Checking available symbols...")
            try:
                symbols = mt5.symbols_get()
                if symbols:
                    print(f"    ✓ {len(symbols)} symbols available")
                    print(f"      Sample: {symbols[0].name if symbols else 'None'}")
                else:
                    print(f"    ✗ No symbols available - network/connection issue")
            except Exception as e:
                print(f"    ✗ Error checking symbols: {e}")
        else:
            err = mt5.last_error()
            print(f"    ✗ Login FAILED")
            print(f"      Error code: {err[0] if err else 'Unknown'}")
            print(f"      Error msg: {err[1] if err else 'Unknown'}")
            print(f"\n    DIAGNOSTIC:")
            print(f"      • Verify account number: {login}")
            print(f"      • Verify password is correct")
            print(f"      • Verify server: {server}")
            print(f"      • Check Terminal window title for correct server name")
            print(f"      • Confirm Terminal is connected to server")
    except Exception as e:
        print(f"    ✗ Exception during login: {e}")
    
    finally:
        # Cleanup
        try:
            mt5.shutdown()
            print(f"\n[7] MT5 shutdown complete")
        except:
            pass
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    print("""
1. Ensure MetaTrader5 Terminal is running
   • Check taskbar or Start Menu
   • If not running, launch it

2. Verify Terminal is connected to server
   • Look for "Connected" indicator in MT5
   • Check internet connection
   • Disable VPN if enabled
   • Check firewall/antivirus isn't blocking MT5

3. Verify credentials
   • Account number (9-digit integer)
   • Password (case-sensitive!)
   • Server name (must match MT5 terminal exactly)
   • Example: "Exness-MT5Trial9" not "Exness" or "exness-mt5trial9"

4. If Terminal shows "Not Connected"
   • Click Tools > Options > Servers tab
   • Verify server settings
   • Try clicking "Connect" button
   • Restart MT5 if necessary

5. Check network
   • Open browser and verify internet works
   • Try pinging broker website: brokersite.com
   • Check if other programs can access internet
""")


if __name__ == "__main__":
    diagnose()
