"""
DTC Dual-Socket Verification Script
Tests the new Dual-Socket DTCClient architecture
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from data_feed.dtc_client import DTCClient
from data_feed.dispatcher import ohlc_buffers

def main():
    print("="*60)
    print("DTC DUAL-SOCKET VERIFICATION")
    print("="*60)
    
    # Initialize client
    client = DTCClient(host="localhost", port_live=11099, port_hist=11098, symbol="XAUUSD")
    
    print("\n[TEST] connect()...")
    success = client.connect()
    
    if not success:
        print("[FAIL] Client failed to connect to critical LIVE socket.")
        return
        
    print(f"[OK] Live Connected: {client.live_connected}")
    print(f"[OK] Hist Connected: {client.hist_connected}")
    
    if not client.hist_connected:
        print("[WARN] Historical socket failed (expected if port 11098 not open).")
        print("       System should still proceed with Live data.")
    
    print("\n[TEST] Starting listeners...")
    client.listen()
    
    print("\n[TEST] Waiting 15 seconds for data flow...")
    start_time = time.time()
    while time.time() - start_time < 15:
        time.sleep(1)
        
        # Check internal flags
        live_status = "READY" if client.live_logon else "Logon..."
        hist_status = "READY" if client.hist_logon else ("Logon..." if client.hist_connected else "FAILED")
        
        print(f"   Status: LIVE={live_status} | HIST={hist_status}")
        
    print("\n[TEST] checking buffers...")
    h1_len = len(ohlc_buffers.get("H1", []))
    m5_len = len(ohlc_buffers.get("M5", []))
    
    print(f"   H1 Candles: {h1_len}")
    print(f"   M5 Candles: {m5_len}")
    
    if h1_len > 0:
        print("[SUCCESS] Data received and processed!")
        print(f"Last H1: {ohlc_buffers['H1'][-1]}")
    else:
        print("[WARN] No data in buffers yet.")
        
    client.running = False
    print("\n[TEST] Complete.")

if __name__ == "__main__":
    main()
