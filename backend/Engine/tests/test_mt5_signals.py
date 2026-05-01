"""
Test ZeroMQ connection and signal sending to MT5 EA.
This script sends test signals to verify the EA is receiving them correctly.
"""

import sys
from pathlib import Path
import time
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Engine.bridge import Bridge

def send_test_signals():
    """Send a series of test signals to the MT5 EA."""
    
    print("=== ZeroMQ MT5 EA Test ===")
    print("Initializing bridge on port 5555...")
    
    try:
        bridge = Bridge(port=5555)
        print("✓ Bridge initialized successfully")
        print("\nWaiting 2 seconds for EA to connect...")
        time.sleep(2)
        
        # Test Signal 1: LONG
        print("\n--- Test 1: LONG Signal ---")
        signal_long = {
            "action": "LONG",
            "symbol": "XAUUSD",
            "price": 2045.50,
            "sl": 2043.50,
            "lots": 0.01,
            "bias": "BULLISH",
            "desc": "Test LONG signal"
        }
        bridge.send_signal(signal_long)
        print(f"Sent: {json.dumps(signal_long, indent=2)}")
        time.sleep(3)
        
        # Test Signal 2: SHORT
        print("\n--- Test 2: SHORT Signal ---")
        signal_short = {
            "action": "SHORT",
            "symbol": "XAUUSD",
            "price": 2050.00,
            "sl": 2052.00,
            "lots": 0.01,
            "bias": "BEARISH",
            "desc": "Test SHORT signal"
        }
        bridge.send_signal(signal_short)
        print(f"Sent: {json.dumps(signal_short, indent=2)}")
        time.sleep(3)
        
        # Test Signal 3: Invalid (should be rejected by EA)
        print("\n--- Test 3: Invalid Signal (should be rejected) ---")
        signal_invalid = {
            "action": "INVALID_ACTION",
            "symbol": "XAUUSD",
            "price": 2045.00,
            "sl": 2043.00,
            "lots": 0.01
        }
        bridge.send_signal(signal_invalid)
        print(f"Sent: {json.dumps(signal_invalid, indent=2)}")
        time.sleep(3)
        
        # Test Signal 4: Excessive lot size (should be rejected)
        print("\n--- Test 4: Excessive Lot Size (should be rejected) ---")
        signal_large = {
            "action": "LONG",
            "symbol": "XAUUSD",
            "price": 2045.00,
            "sl": 2043.00,
            "lots": 100.0,  # Exceeds MAX_LOT_SIZE
            "bias": "BULLISH"
        }
        bridge.send_signal(signal_large)
        print(f"Sent: {json.dumps(signal_large, indent=2)}")
        time.sleep(3)
        
        print("\n=== Test Complete ===")
        print("\nCheck MT5 Experts log to verify:")
        print("  1. All signals were received")
        print("  2. Valid signals (1 & 2) were processed")
        print("  3. Invalid signals (3 & 4) were rejected with appropriate errors")
        
        bridge.close()
        print("\n✓ Bridge closed")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    send_test_signals()
