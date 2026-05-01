"""
Simple DTC Connection Test (No Unicode)
Tests Sierra Chart DTC connection without emoji characters
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import threading

def main():
    print("=" * 60)
    print("DTC CONNECTION TEST")
    print("=" * 60)
    
    # Step 1: Import DTC Client
    try:
        from data_feed import dtc_client
        print("[OK] DTC client module imported")
    except ImportError as e:
        print(f"[FAIL] Failed to import DTC client: {e}")
        return
    
    # Step 2: Create client
    try:
        client = dtc_client.DTCClient(host="localhost", port=11099, symbol="XAUUSD")
        print("[OK] DTC client instance created")
    except Exception as e:
        print(f"[FAIL] Failed to create client: {e}")
        return
    
    # Step 3: Test connection
    print("\n[TEST] Attempting DTC connection to localhost:11099...")
    if client.connect():
        print("[OK] Socket connected successfully")
        print(f"[INFO] Connection state - Logon accepted: {client.logon_accepted}")
        print(f"[INFO] Connection state - Subscription active: {client.subscription_active}")
    else:
        print("[FAIL] DTC connection FAILED")
        print("\nTroubleshooting:")
        print("  1. Ensure Sierra Chart is running")
        print("  2. Open: Global Settings -> Data/Trade Service Settings")
        print("  3. Check: 'DTC Protocol Server' is enabled")
        print("  4. Check: Port is set to 11099")
        return
    
    # Step 4: Listen for data
    print("\n[TEST] Starting listener thread...")
    print("        Waiting 15 seconds for data...")
    
    listen_thread = threading.Thread(target=client.listen, daemon=True)
    listen_thread.start()
    
    # Wait for data
    for i in range(15):
        time.sleep(1)
        if client.logon_accepted:
            print(f"        [{i+1}s] Logon accepted! Waiting for data...")
        else:
            print(f"        [{i+1}s] Waiting for logon response...")
    
    # Step 5: Check buffers
    print("\n[TEST] Checking buffer population...")
    try:
        from data_feed.dispatcher import ohlc_buffers, delta_buffers
        
        h1_count = len(ohlc_buffers.get('H1', []))
        m15_count = len(ohlc_buffers.get('M15', []))
        m5_count = len(ohlc_buffers.get('M5', []))
        delta_count = len(delta_buffers.get('M5', []))
        
        print(f"\nBuffer Status:")
        print(f"  H1  OHLC:  {h1_count:>3} candles {'[OK]' if h1_count > 0 else '[EMPTY]'}")
        print(f"  M15 OHLC:  {m15_count:>3} candles {'[OK]' if m15_count > 0 else '[EMPTY]'}")
        print(f"  M5  OHLC:  {m5_count:>3} candles {'[OK]' if m5_count > 0 else '[EMPTY]'}")
        print(f"  M5  Delta: {delta_count:>3} values {'[OK]' if delta_count > 0 else '[EMPTY]'}")
        
        # Connection state
        print(f"\nConnection State:")
        print(f"  Logon accepted: {client.logon_accepted}")
        print(f"  Subscription active: {client.subscription_active}")
        print(f"  Client running: {client.running}")
        
        # Sample data
        if h1_count > 0:
            print("\n[TEST] Sample H1 candle (most recent):")
            sample = list(ohlc_buffers['H1'])[-1]
            for key, val in sample.items():
                print(f"  {key}: {val}")
        
        # Results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        
        if h1_count >= 24 and m15_count >= 96 and m5_count >= 288:
            print("[SUCCESS] DTC CONNECTION IS WORKING")
            print("[SUCCESS] Sufficient historical data received")
            print(f"\nData loaded:")
            print(f"  H1:  {h1_count} candles (target: 24+)")
            print(f"  M15: {m15_count} candles (target: 96+)")
            print(f"  M5:  {m5_count} candles (target: 288+)")
        elif h1_count > 0:
            print("[PARTIAL] DTC CONNECTED BUT INSUFFICIENT DATA")
            print(f"  H1 bars: {h1_count} / 24 minimum needed")
            print("\nPossible causes:")
            print("  1. Sierra Chart doesn't have enough data loaded")
            print("  2. Historical data request is failing")
            print("  3. Still loading (wait 30 more seconds)")
        elif client.logon_accepted:
            print("[WARNING] DTC LOGON SUCCESSFUL BUT NO DATA")
            print("\nPossible causes:")
            print("  1. Historical data request format issue")
            print("  2. Sierra Chart symbol mismatch (check 'XAUUSD')")
            print("  3. Market data subscription failed")
        else:
            print("[FAIL] DTC CONNECTED BUT LOGON FAILED")
            print("\nPossible causes:")
            print("  1. Protocol version mismatch")
            print("  2. Authentication required")
            print("  3. Sierra Chart rejected connection")
            
    except Exception as e:
        print(f"[ERROR] Buffer check failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    client.running = False
    if client.sock:
        try:
            client.sock.close()
        except:
            pass
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
