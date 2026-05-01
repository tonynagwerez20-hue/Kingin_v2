"""
DTC Connection Diagnostic Tool
Verifies Sierra Chart DTC connection and buffer population
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import threading

def main():
    print("="*60)
    print("DTC CONNECTION DIAGNOSTIC")
    print("="*60)
    
    # Step 1: Import DTC Client
    try:
        from data_feed import dtc_client
        print("✅ DTC client module imported")
    except ImportError as e:
        print(f"❌ Failed to import DTC client: {e}")
        return
    
    # Step 2: Create client instance
    try:
        client = dtc_client.DTCClient(host="localhost", port_live=11099, symbol="XAUUSD")
        print("✅ DTC client instance created")
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return
    
    # Step 3: Attempt connection
    print("\n[TEST] Attempting DTC connection to localhost:11099...")
    if client.connect():
        print("✅ Socket connected successfully")
    else:
        print("❌ DTC connection FAILED")
        print("\nTroubleshooting:")
        print("  1. Ensure Sierra Chart is running")
        print("  2. Open: Global Settings → DTC Service Settings")
        print("  3. Check: 'Enable DTC Server' is enabled")
        print("  4. Check: Port is set to 11099")
        print("  5. Check: Windows Firewall allows port 11099")
        return
    
    # Step 4: Listen for data
    print("\n[TEST] Starting listener thread...")
    print("       Waiting 15 seconds for historical data...")
    
    listen_thread = threading.Thread(target=client.listen, daemon=True)
    listen_thread.start()
    
    # Wait for data to arrive
    time.sleep(15)
    
    # Step 5: Check buffers
    print("\n[TEST] Checking buffer population...")
    try:
        from data_feed.dispatcher import ohlc_buffers, delta_buffers
        
        h1_count = len(ohlc_buffers.get('H1', []))
        m15_count = len(ohlc_buffers.get('M15', []))
        m5_count = len(ohlc_buffers.get('M5', []))
        delta_count = len(delta_buffers.get('M5', []))
        
        print(f"\nBuffer Status:")
        print(f"  H1  OHLC:  {h1_count:>3} candles {'✅' if h1_count > 0 else '❌'}")
        print(f"  M15 OHLC:  {m15_count:>3} candles {'✅' if m15_count > 0 else '❌'}")
        print(f"  M5  OHLC:  {m5_count:>3} candles {'✅' if m5_count > 0 else '❌'}")
        print(f"  M5  Delta: {delta_count:>3} values {'✅' if delta_count > 0 else '❌'}")
        
        # Step 6: Sample data inspection
        if h1_count > 0:
            print("\n[TEST] Sample H1 candle (most recent):")
            sample = list(ohlc_buffers['H1'])[-1]
            print(f"  Time:  {sample.get('time', 'N/A')}")
            print(f"  Open:  {sample.get('open', 'N/A')}")
            print(f"  High:  {sample.get('high', 'N/A')}")
            print(f"  Low:   {sample.get('low', 'N/A')}")
            print(f"  Close: {sample.get('close', 'N/A')}")
            print(f"  Delta: {sample.get('delta', 'N/A')}")
        
        # Step 7: Overall assessment
        print("\n" + "="*60)
        print("DIAGNOSTIC RESULTS")
        print("="*60)
        
        if h1_count >= 24 and m15_count >= 96 and m5_count >= 288:
            print("✅ DTC CONNECTION IS WORKING")
            print("✅ Sufficient historical data received")
            print("\nNext steps:")
            print("  1. Check why signals aren't being generated")
            print("  2. Run: python tests/test_strategy_signal.py")
            print("  3. Enable verbose logging in main_loop.py")
        elif h1_count > 0:
            print("⚠️  DTC CONNECTED BUT INSUFFICIENT DATA")
            print(f"   H1 bars: {h1_count}/24 minimum")
            print("\nPossible causes:")
            print("  1. Sierra Chart doesn't have enough data loaded")
            print("  2. Historical data request is failing")
            print("  3. Need to increase data window from 1 to 5 days")
        else:
            print("❌ DTC CONNECTED BUT NO DATA RECEIVED")
            print("\nTroubleshooting:")
            print("  1. Check Sierra Chart has XAUUSD chart loaded")
            print("  2. Check chart has at least 1 day of data")
            print("  3. Check Sierra's message log for errors")
            print("  4. Try manual trade in Sierra to verify data feed")
            
    except Exception as e:
        print(f"❌ Error checking buffers: {e}")
        import traceback
        traceback.print_exc()
    
    # Clean up
    client.running = False
    if client.sock:
        try:
            client.sock.close()
        except:
            pass
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
