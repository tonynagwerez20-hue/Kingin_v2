"""System Health Diagnostic Tool

Tests all critical connections before starting the trading system:
1. Sierra Chart DTC connection
2. MT5 ZMQ bridge
3. Data Feed API
4. Database connectivity

Run this BEFORE starting the trading engine to verify all components are ready.
"""

import sys
import socket
import time
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}[OK] {text}{RESET}")

def print_error(text):
    print(f"{RED}[ERROR] {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}[WARN] {text}{RESET}")

def test_sierra_chart_dtc():
    """Test Sierra Chart DTC server connectivity"""
    print_header("Sierra Chart DTC Connection")
    
    host = "127.0.0.1"
    port_live = 11099
    port_hist = 11098
    
    # Test Live Port
    try:
        sock = socket.create_connection((host, port_live), timeout=3)
        sock.close()
        print_success(f"DTC Live Port ({port_live}): REACHABLE")
        live_ok = True
    except Exception as e:
        print_error(f"DTC Live Port ({port_live}): UNREACHABLE")
        print(f"   Error: {e}")
        print_warning("   Fix: Ensure Sierra Chart is running with DTC server enabled")
        live_ok = False
    
    # Test Historical Port
    try:
        sock = socket.create_connection((host, port_hist), timeout=3)
        sock.close()
        print_success(f"DTC Historical Port ({port_hist}): REACHABLE")
        hist_ok = True
    except Exception as e:
        print_error(f"DTC Historical Port ({port_hist}): UNREACHABLE")
        print(f"   Error: {e}")
        print_warning("   Fix: Check Sierra Chart DTC server settings")
        hist_ok = False
    
    # Test DTC Login (if ports are reachable)
    if live_ok:
        try:
            from data_feed.dtc_client import DTCClient
            print("\nTesting DTC Login...")
            client = DTCClient(host=host, port_live=port_live, skip_history=True)
            client.start()
            time.sleep(3)  # Wait for login
            
            if client.live_logon:
                print_success("DTC Login: SUCCESS")
                
                # Check trading support
                print_warning("Note: 'TradingIsSupported' in Sierra Chart logs")
                print("   If using MT5 for execution: TradingIsSupported: 0 is OK")
                print("   If using Sierra Chart for execution: Must be 1")
                print("   Check Sierra Chart logs for actual value")
            else:
                print_error("DTC Login: FAILED")
                print_warning("   Fix: Check Sierra Chart DTC server is running")
            
            client.running = False
            client._disconnect_all()
        except Exception as e:
            print_error(f"DTC Login Test: FAILED - {e}")
    
    return live_ok and hist_ok

def test_mt5_bridge():
    """Test MT5 ZMQ bridge connectivity"""
    print_header("MetaTrader 5 Bridge")
    
    try:
        from execution.bridge import Bridge
        
        print("Initializing MT5 Bridge...")
        bridge = Bridge(pub_port=5555, req_port=5557)
        
        if not bridge.connected:
            print_error("MT5 Bridge: NOT CONNECTED")
            print_warning("   Fix: Ensure MT5 is running with EA attached")
            print_warning("   Fix: Enable 'Algo Trading' (green button)")
            print_warning("   Fix: Allow DLL imports in MT5 settings")
            return False
        
        print_success("MT5 Bridge: CONNECTED")
        
        # Test heartbeat
        print("\nTesting heartbeat...")
        heartbeat = bridge.check_connection()
        if heartbeat:
            print_success("Heartbeat: OK - MT5 Respond Correct")
        else:
            print_error("Heartbeat: NO RESPONSE")
            print_warning("   Fix: Check MT5 EA is running (smiley face icon)")
            return False
        
        # Test balance fetch
        print("\nFetching account balance...")
        balance = bridge.get_account_balance()
        if balance is not None:
            print_success(f"Account Balance: ${balance:,.2f}")
        else:
            print_error("Account Balance: TIMEOUT")
            print_warning("   Fix: Check MT5 EA 'Experts' tab for errors")
            return False
        
        return True
        
    except ImportError as e:
        print_error(f"MT5 Bridge: MODULE NOT FOUND - {e}")
        print_warning("   Fix: Ensure execution/bridge.py exists")
        return False
    except Exception as e:
        print_error(f"MT5 Bridge: ERROR - {e}")
        return False

def test_data_feed_api():
    """Test Data Feed API connectivity"""
    print_header("Data Feed API")
    
    api_url = "http://localhost:8000"
    
    # Test /status endpoint
    try:
        resp = requests.get(f"{api_url}/status", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print_success(f"API Status: {data.get('mode', 'UNKNOWN')}")
            print(f"   State: {data.get('state', 'N/A')}")
            print(f"   Synced: {data.get('is_synced', False)}")
        else:
            print_error(f"API Status: HTTP {resp.status_code}")
    except Exception as e:
        print_error(f"API Status: UNREACHABLE - {e}")
        print_warning("   Fix: Start data_feed/server.py")
        return False
    
    # Test /latest-tick endpoint
    try:
        resp = requests.get(f"{api_url}/latest-tick", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get('price', 0)
            if price > 0:
                print_success(f"Latest Price: {price:.2f}")
                print(f"   Bid: {data.get('bid', 0):.2f}")
                print(f"   Ask: {data.get('ask', 0):.2f}")
                print(f"   Volume: {data.get('volume', 0):,.0f}")
            else:
                print_warning("Latest Price: No data available yet")
                print("   Wait for DTC to sync historical data")
        else:
            print_error(f"Latest Tick: HTTP {resp.status_code}")
    except Exception as e:
        print_error(f"Latest Tick: ERROR - {e}")
        return False
    
    return True

def test_database():
    """Test database connectivity"""
    print_header("Database Connectivity")
    
    try:
        from storage.hedge_db import HedgeDB
        
        db = HedgeDB("data/hedge.db")
        
        # Test read
        balance = db.get_state("account_balance", 0)
        print_success(f"Database: CONNECTED")
        print(f"   Stored Balance: ${balance:,.2f}")
        
        # Test write
        db.set_state("health_check", time.time())
        print_success("Database: READ/WRITE OK")
        
        db.close()
        return True
        
    except Exception as e:
        print_error(f"Database: ERROR - {e}")
        return False

def main():
    print(f"\n{BLUE}{'#'*60}{RESET}")
    print(f"{BLUE}#{'SYSTEM HEALTH DIAGNOSTIC'.center(58)}#{RESET}")
    print(f"{BLUE}#{'Run this before starting the trading engine'.center(58)}#{RESET}")
    print(f"{BLUE}{'#'*60}{RESET}")
    
    results = {}
    
    # Run all tests
    results['dtc'] = test_sierra_chart_dtc()
    results['mt5'] = test_mt5_bridge()
    results['api'] = test_data_feed_api()
    results['db'] = test_database()
    
    # Summary
    print_header("DIAGNOSTIC SUMMARY")
    
    all_passed = all(results.values())
    
    if all_passed:
        print_success("ALL SYSTEMS OPERATIONAL [DONE]")
        print("\nYou can now start the trading engine:")
        print(f"   {BLUE}python Engine/main_loop.py{RESET}")
    else:
        print_error("SYSTEM NOT READY [FAIL]")
        print("\nFailed components:")
        for component, status in results.items():
            if not status:
                print(f"   {RED}* {component.upper()}{RESET}")
        
        print("\n" + "="*60)
        print("TROUBLESHOOTING CHECKLIST:")
        print("="*60)
        print("\n1. Sierra Chart:")
        print("   [ ] Run as Administrator")
        print("   [ ] Windows Firewall allows SierraChart_64.exe")
        print("   [ ] DTC Protocol Server enabled")
        print("   [ ] 'Allow Trading' checked in DTC settings")
        print("   [ ] VPN disabled (if applicable)")
        
        print("\n2. MetaTrader 5:")
        print("   [ ] Algo Trading enabled (green button)")
        print("   [ ] Allow DLL imports in settings")
        print("   [ ] EA shows smiley face (not sad face icon)")
        print("   [ ] VC++ Redistributable installed")
        
        print("\n3. Data Feed:")
        print("   [ ] server.py is running")
        print("   [ ] Port 8000 not blocked by firewall")
        
        print(f"\n{YELLOW}See implementation_plan.md for detailed fix instructions{RESET}\n")

if __name__ == "__main__":
    main()
