"""
Test script for v5.3 MT5 Integration features.
Tests Bridge acknowledgment and balance fetching.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from execution.bridge import Bridge
import time

def test_bridge_connection():
    """Test basic Bridge connection and heartbeat."""
    print("=" * 60)
    print("Testing v5.3 Bridge Features")
    print("=" * 60)
    
    # Initialize Bridge
    print("\n1. Initializing Bridge...")
    bridge = Bridge(pub_port=5555, req_port=5557)
    
    # Test connection
    print("\n2. Testing MT5 connection...")
    if bridge.check_connection():
        print("   ✓ MT5 EA is responding")
    else:
        print("   ✗ MT5 EA not responding (ensure EA is running)")
        return
    
    # Test balance fetching
    print("\n3. Testing account balance fetching...")
    balance = bridge.get_account_balance()
    if balance is not None:
        print(f"   ✓ Account Balance: ${balance:.2f}")
    else:
        print("   ✗ Failed to fetch balance")
    
    # Test signal with acknowledgment
    print("\n4. Testing signal with acknowledgment...")
    test_signal = {
        "action": "LONG",
        "symbol": "XAUUSD",
        "price": 2045.50,
        "sl": 2042.00,
        "lots": 0.01,  # Small lot for testing
        "desc": "Test signal from v5.3 test script"
    }
    
    print(f"   Sending test signal: {test_signal['action']} {test_signal['lots']} lots")
    ack = bridge.send_signal_with_ack(test_signal, timeout=5, max_retries=2)
    
    if ack.get("status") == "SUCCESS":
        print(f"   ✓ Signal acknowledged!")
        print(f"     Ticket: {ack.get('ticket')}")
        print(f"     Execution Price: {ack.get('execution_price')}")
        print(f"     Timestamp: {ack.get('timestamp')}")
    elif ack.get("status") == "FAILED":
        print(f"   ✗ Signal failed: {ack.get('error')}")
    else:
        print(f"   ✗ Timeout or error: {ack}")
    
    # Test fire-and-forget (backward compatibility)
    print("\n5. Testing backward-compatible fire-and-forget...")
    bridge.send_signal(test_signal)
    print("   ✓ Signal sent (no acknowledgment expected)")
    
    # Cleanup
    print("\n6. Cleaning up...")
    bridge.close()
    print("   ✓ Bridge closed")
    
    print("\n" + "=" * 60)
    print("v5.3 Bridge Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Ensure MT5 with HedgeEA is running before starting this test!\n")
    input("Press Enter to continue...")
    
    try:
        test_bridge_connection()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
