"""
SOLUTION - Multi-Broker Account Detection

This file explains how the system now automatically detects and works with
any MT5 account on any broker, without hardcoding credentials.

BEFORE (Hardcoded - Only worked with one specific Exness account):
- Config had: login=435341374, server="Exness-MT5Trial9"
- System couldn't work with other brokers or accounts
- Every user had to manually edit credentials

AFTER (Dynamic - Works with any broker/account):
- System auto-detects the currently logged-in MT5 account
- Works with Exness, ICMarkets, Pepperstone, OANDA, etc.
- No manual credential editing needed
- Multi-account capable

HOW IT WORKS NOW:

1. User opens MetaTrader5 and logs in with any account (any broker)
2. User runs START_SYSTEM_SMART.bat
3. Engine launcher automatically:
   - Detects the active MT5 account
   - Reads account details (balance, leverage, etc.)
   - Updates trading_params_lite.json with current account info
   - Starts the dashboard with live data from that account
4. Dashboard receives live streaming data specific to the logged-in account

KEY FILES:

1. mt5_account_detector.py
   - AccountDetector class that handles auto-detection
   - Detects any MT5 account and extracts broker info
   - Falls back to saved credentials if MT5 not running
   
2. engine_launcher.py
   - Intelligent startup sequence
   - Uses AccountDetector to initialize system
   - Creates engine_state.json for dashboard to read
   - Handles both live and demo modes
   
3. trading_params_lite.json (UPDATED)
   - Removed hardcoded Exness credentials
   - Now uses: "auto_detect": true
   - login/password/server set to null (auto-filled at runtime)

4. START_SYSTEM_SMART.bat
   - New startup script that users should use
   - Runs engine_launcher.py first
   - Then launches the dashboard

SUPPORTED BROKERS (Automatic Detection):

The system automatically recognizes and works with:
- Exness (all variants: Trial, Live, etc.)
- ICMarkets
- Pepperstone
- OANDA
- FXPrimus
- Just2Trade
- EasyMarkets
- Hantec
- Any other MT5 broker (detected as "Unknown" but still works)

USAGE INSTRUCTIONS:

STEP 1: Open MetaTrader5
- Launch your MT5 terminal with your account
- Log in to any broker you use (Exness, ICMarkets, etc.)
- Wait for full connection

STEP 2: Run the Smart Startup Script
Option A (Recommended): Double-click START_SYSTEM_SMART.bat
Option B: Open PowerShell and run: python engine_launcher.py

STEP 3: Watch the Dashboard Initialize
- System will auto-detect your account
- Config will update automatically
- Dashboard will show "LIVE" status
- Data will stream from your actual MT5 account

TROUBLESHOOTING:

Q: "No active MT5 account detected"
A: Make sure MetaTrader5 is open and fully connected before running the startup script

Q: "Error -6: Terminal: Authorization failed"
A: Enable "Allow automated trading" in MT5 (Tools → Options → Expert Advisors tab)

Q: "Different broker than I expected"
A: The system detects the broker from the MT5 server name. Verify your login is with the correct broker.

Q: Can I use multiple accounts?
A: Yes! Just log into a different account in MT5 and run START_SYSTEM_SMART.bat again. It will auto-detect the new account.

WHAT'S DIFFERENT FROM BEFORE:

Before:
- Had to manually edit trading_params_lite.json with credentials
- Only worked with hardcoded Exness account
- Dashboard received fake/hardcoded data
- Multiple users/accounts wasn't possible

Now:
- Credentials auto-detected from active MT5 session
- Works with any MT5 broker
- Dashboard receives LIVE real data from your account
- Each user can use their own account without config changes
- Accounts can be switched by logging in with different MT5 account

DEVELOPER NOTES:

The system follows this initialization flow:

START_SYSTEM_SMART.bat
    ↓
engine_launcher.py (EngineLauncher.initialize())
    ↓
mt5_account_detector.py (AccountDetector.get_active_credentials())
    ↓
1. Check for active MT5 account (any broker)
2. If found, return {login, server, broker, balance, leverage}
3. If not running, fallback to saved runtime_credentials.json
    ↓
Update trading_params_lite.json with detected credentials
    ↓
Initialize MT5 with the correct account
    ↓
Create engine_state.json with live account data
    ↓
Dashboard reads engine_state.json (refreshes every 2 seconds)
    ↓
User sees LIVE data from their actual MT5 account

This architecture ensures:
- No hardcoding of credentials
- Works with any broker/account
- Automatic switching when user logs into different account
- Backwards compatibility with saved credentials
- Clean separation of concerns
"""