"""
Quick MT5 Connection Test with Timeout
"""

import sys
import time
import signal

def timeout_handler(signum, frame):
    print("TIMEOUT: MT5 not responding")
    sys.exit(1)

# Set 10 second timeout
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)

try:
    print("Testing MT5 connection (10 second timeout)...")
    import MetaTrader5 as mt5
    print(f"MT5 version: {mt5.__version__}")

    print("Initializing...")
    result = mt5.initialize()
    print(f"Initialize result: {result}")

    if result:
        print("SUCCESS: MT5 connected!")
        terminal_info = mt5.terminal_info()
        if terminal_info:
            print(f"Terminal: {terminal_info.server}")
            print(f"Connected: {terminal_info.connected}")
            print(f"Trade allowed: {terminal_info.trade_allowed}")
        mt5.shutdown()
    else:
        error = mt5.last_error()
        print(f"FAILED: {error}")

except Exception as e:
    print(f"ERROR: {e}")

signal.alarm(0)  # Cancel timeout