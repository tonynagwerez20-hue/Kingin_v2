import MetaTrader5 as mt5
import time

print("Testing MT5 connection...")
print(f"MT5 version: {mt5.__version__}")

# Try to initialize
result = mt5.initialize()
print(f"Initialize result: {result}")

if not result:
    error = mt5.last_error()
    print(f"Last error: {error}")

    if error[0] == -6:
        print("Authorization failed - this usually means:")
        print("1. Automated trading is not enabled in MT5")
        print("2. MT5 terminal needs to be restarted")
        print("3. MT5 needs to run as administrator")
else:
    print("MT5 initialized successfully!")
    terminal_info = mt5.terminal_info()
    if terminal_info:
        print(f"Terminal connected: {terminal_info.connected}")
        print(f"Trade allowed: {terminal_info.trade_allowed}")

mt5.shutdown()