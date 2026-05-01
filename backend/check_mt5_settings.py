import MetaTrader5 as mt5
import os

def check_mt5_settings():
    """Check MT5 terminal settings and enable automated trading if needed"""

    # Initialize MT5
    if not mt5.initialize():
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return False

    try:
        # Get terminal info
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            print(f"Failed to get terminal info: {mt5.last_error()}")
            return False

        print(f"Terminal connected: {terminal_info.connected}")
        print(f"Trade allowed: {terminal_info.trade_allowed}")
        print(f"Trade API: {terminal_info.tradeapi_disabled}")

        # Check if automated trading is enabled
        if not terminal_info.trade_allowed:
            print("Automated trading is disabled. Attempting to enable...")

            # Try to enable automated trading
            # This might require manual intervention in MT5 terminal
            print("Please enable 'Algo Trading' in MT5 terminal:")
            print("1. Open MT5 terminal")
            print("2. Go to Tools -> Options -> Expert Advisors")
            print("3. Check 'Allow automated trading'")
            print("4. Check 'Allow DLL imports'")
            print("5. Check 'Allow external experts imports'")
            print("6. Restart MT5 terminal")

        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")

        if not login or not password or not server:
            print("Set MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER environment variables to test login.")
            return bool(terminal_info.connected)

        login_result = mt5.login(int(login), password=password, server=server)
        if login_result:
            print("Login successful!")
            account_info = mt5.account_info()
            if account_info:
                print(f"Account: {account_info.login}, Balance: {account_info.balance}")
            return True
        else:
            print(f"Login failed: {mt5.last_error()}")
            return False

    finally:
        mt5.shutdown()

if __name__ == "__main__":
    check_mt5_settings()