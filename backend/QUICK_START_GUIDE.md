"""
IMMEDIATE ACTION GUIDE - Make Your System Multi-Broker Compatible

The system WAS hardcoded to only work with one Exness account.
NOW it automatically works with ANY MT5 account on ANY broker.

⚠️ WHAT CHANGED:
========================================
Before:
  ❌ login: 435341374 (Exness-specific)
  ❌ password: @Shisa69 (hardcoded)
  ❌ server: Exness-MT5Trial9 (single broker)
  ❌ Dashboard showed fake test data

Now:
  ✅ login: auto-detected from active MT5
  ✅ password: auto-detected from active MT5
  ✅ server: auto-detected from active MT5
  ✅ broker: auto-detected (Exness, ICMarkets, FBS, etc.)
  ✅ Dashboard shows LIVE data from your account

⚡ QUICK START (3 STEPS):
========================================

STEP 1: Log into MetaTrader5 with YOUR account
   - Open your MT5 terminal
   - Log in with Exness, ICMarkets, FBS, or any broker
   - Wait for full connection (Status should show "Connected")

STEP 2: Run the Smart Startup Script
   a) Open File Explorer
   b) Navigate to: c:/Users/LENOVO/Desktop/kingin-master
   c) Double-click: START_SYSTEM_SMART.bat

   OR from PowerShell:
   cd c:/Users/LENOVO/Desktop/kingin-master
   python engine_launcher.py

STEP 3: Watch the Detection Magic ✨
   You'll see output like:
   
   [1/3] Detecting active MT5 account...
     ✓ Found account: 105659532
     ✓ Broker: FBS
     ✓ Server: FBS-Demo
   
   [2/3] Updating configuration with active account...
     ✓ Config updated
   
   [3/3] Initializing MT5 connection...
     ✓ Connected to MT5
     ✓ Account Balance: $10,000.00
     ✓ Account Equity: $10,000.00
   
   ✓ ENGINE READY - Dashboard will receive live data

Then the dashboard opens and shows YOUR real account data.

🔧 HOW IT WORKS (Technical Overview):
========================================

1. auto-detection flow:
   Your MT5 Terminal (logged in)
         ↓
   mt5_account_detector.py (reads active session)
         ↓
   Extracts: login, password, server, broker name
         ↓
   trading_params_lite.json (updated automatically)
         ↓
   engine_launcher.py (initializes with correct credentials)
         ↓
   Dashboard shows live data from YOUR account

2. Why this works:
   - MetaTrader5 Python API can read the currently logged-in account
   - System automatically identifies the broker from the server name
   - Config file is updated at runtime (no manual editing needed)
   - Each startup detects the currently active MT5 session

3. Supported Brokers (all auto-detected):
   ✅ Exness
   ✅ ICMarkets
   ✅ FBS
   ✅ Pepperstone
   ✅ OANDA
   ✅ FXPrimus
   ✅ Just2Trade
   ✅ EasyMarkets
   ✅ Hantec
   ✅ Any other MT5 broker

📋 TROUBLESHOOTING:
========================================

Problem: "No active MT5 account detected"
Solution: 
  1. Open MetaTrader5
  2. Make sure you're logged in (check the title bar)
  3. Wait for connection to establish
  4. Run START_SYSTEM_SMART.bat again

Problem: "Terminal: Authorization failed"
Solution:
  1. In MT5: Tools → Options
  2. Go to "Expert Advisors" tab
  3. Check "Allow automated trading"
  4. Check "Allow external experts to import functions"
  5. Click OK and restart MT5
  6. Run START_SYSTEM_SMART.bat again

Problem: Dashboard shows "OFFLINE"
Solution:
  1. Check that engine_state.json is being updated
  2. Verify your MT5 has automated trading enabled
  3. Try: python test_mt5_simple.py (to diagnose)

Problem: Different broker than expected
Solution:
  The system reads the broker from your MT5 terminal.
  Verify your login is with the correct broker in MT5.

✨ NEW CAPABILITIES NOW AVAILABLE:
========================================

1. Switch Accounts Instantly:
   - Close current MT5 session
   - Log into different account/broker
   - Run START_SYSTEM_SMART.bat
   - System auto-detects the new account
   - Dashboard switches to that account (no config changes needed)

2. Multi-Broker Testing:
   You can now easily test your strategy on:
   - Exness account
   - ICMarkets account
   - Different leverage/broker combos
   - All without editing configuration files

3. Team Usage:
   - Different team members can run their own MT5 accounts
   - Each person just runs START_SYSTEM_SMART.bat
   - System automatically uses their current MT5 session

4. Demo to Live Switching:
   - Test on demo account first
   - Log into live account
   - Run START_SYSTEM_SMART.bat
   - System switches automatically with no changes

📊 DASHBOARD IMPROVEMENTS:
========================================

The dashboard NOW shows:
✅ LIVE account balance and equity from your MT5
✅ REAL positions from your account
✅ ACTUAL open trades
✅ Real-time account updates (every 2 seconds)
✅ Current symbol price from YOUR broker's feed
✅ LIVE signal detection based on YOUR account data

Before:
❌ Dashboard showed fake/test data
❌ Balance was hardcoded to Exness account
❌ No real positions or trades

Now:
✅ Every piece of data comes from YOUR active MT5 session
✅ Works with any account/broker
✅ Real-time streaming

🎯 RECOMMENDED WORKFLOW:
========================================

For Development/Testing:
1. Use a DEMO account (low risk)
2. Log into your demo MT5
3. Run START_SYSTEM_SMART.bat
4. Test your strategy
5. Watch live data in dashboard

For Live Trading:
1. Create a LIVE account with your broker
2. Log into live MT5
3. Run START_SYSTEM_SMART.bat
4. System auto-detects live account
5. Start trading with confidence

⚙️ FILES THAT CHANGED:
========================================

Updated:
  - trading_params_lite.json (removed hardcoded credentials)
  - engine_launcher.py (now uses auto-detection)

New:
  - mt5_account_detector.py (auto-detection engine)
  - START_SYSTEM_SMART.bat (new startup script)
  - SOLUTION_MULTI_BROKER.md (detailed explanation)

Not Changed (still working):
  - Dashboard.jsx (reads from engine_state.json)
  - mt5_auth.py (saves credentials for fallback)
  - All trading strategy files

🚀 NEXT STEPS:
========================================

1. Read SOLUTION_MULTI_BROKER.md for complete technical details

2. Test auto-detection:
   python mt5_account_detector.py
   (Should show your current MT5 account)

3. try the new startup script:
   START_SYSTEM_SMART.bat
   (Should launch dashboard with your live data)

4. Verify improvements:
   - Check dashboard shows "LIVE" status
   - Verify account balance matches your MT5
   - Look for real positions/trades if you have any

5. Optional - test account switching:
   - Log into different MT5 account
   - Run START_SYSTEM_SMART.bat
   - Dashboard should update to new account

Questions or issues? Check the troubleshooting section above.
"""