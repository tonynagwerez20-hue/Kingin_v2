"""
IPC TIMEOUT RESOLUTION GUIDE
Maintaining Multi-Broker Auto-Detection Improvements

ERROR: "IPC timeout (4 attempts remaining)"
CAUSE: MetaTrader5 Python API cannot communicate with MT5 terminal
SOLUTION: Follow the recovery steps below
"""

# QUICK FIXES (Try these first)

QUICK_FIX_1: Restart MT5 Completely
  1. Close MetaTrader5 completely (File → Exit or Alt+F4)
  2. Wait 5 seconds
  3. Reopen MT5 (double-click desktop shortcut or Start menu)
  4. Wait for full connection (check status bar)
  5. Run: START_ENHANCED.bat

QUICK_FIX_2: Enable Automated Trading
  1. In MetaTrader5, go to: Tools → Options
  2. Click the "Expert Advisors" tab
  3. Check all these boxes:
     ✓ Allow automated trading
     ✓ Allow DLL imports  
     ✓ Allow external experts to import functions
  4. Click OK
  5. Restart MT5
  6. Run: START_ENHANCED.bat

QUICK_FIX_3: Use the Recovery Script
  1. Open PowerShell
  2. cd c:\Users\LENOVO\Desktop\kingin-master
  3. python mt5_recovery.py
  4. Then run: START_ENHANCED.bat

# AUTOMATIC RECOVERY (Recommended)

Use the new START_ENHANCED.bat script which:
  1. Checks if MT5 is running
  2. Starts MT5 if needed (30 second initialization)
  3. Attempts normal startup
  4. If IPC timeout occurs, automatically runs recovery sequence
  5. Attempts startup again after recovery
  6. Launches dashboard if successful

# UNDERSTAND THE ISSUE

What causes "IPC timeout"?
  ┌─────────────────────────────────────┐
  │ Python Code (Your System)           │
  │         ↓ (tries to talk via IPC)   │
  │ MT5 Terminal                        │
  │         ↓ (no response)             │
  │ TIMEOUT! (IPC = Inter-Process Comm) │
  └─────────────────────────────────────┘

Common reasons MT5 doesn't respond:
  1. MT5 terminal not running
  2. MT5 terminal frozen or hung
  3. Automated trading not enabled
  4. MT5 busy with internal updates
  5. Network latency issue
  6. MT5 corrupted/needs reinstall

# STEP-BY-STEP RESOLUTION

STEP 1: Kill All MT5 Processes
  Open PowerShell and run:
  
  taskkill /IM terminal64.exe /F
  taskkill /IM terminal32.exe /F
  taskkill /IM metaeditor64.exe /F
  
  Wait 5 seconds

STEP 2: Clear MT5 Lock Files (optional but recommended)
  1. Press Win+R
  2. Type: %APPDATA%\MetaQuotes\Terminal
  3. Look for files/folders with your MT5 profile
  4. Delete {PROFILE_NAME}.lck file if it exists

STEP 3: Start Fresh MT5
  1. Open "C:\Program Files\MetaTrader 5\terminal64.exe"
  2. Wait for full login and connection
  3. Verify you see the green "Connected" indicator
  4. Verify account is logged in (check window title bar)

STEP 4: Enable Automated Trading
  This is CRITICAL for Python API access:
  
  1. Tools → Options
  2. Expert Advisors tab
  3. Enable:
     ✓ Allow automated trading
     ✓ Allow DLL imports
     ✓ Allow external experts to import functions
  4. OK
  5. Restart MT5

STEP 5: Test Python Connection
  PowerShell:
  
  cd c:\Users\LENOVO\Desktop\kingin-master
  python test_mt5_simple.py
  
  Expected output:
    Testing MT5 connection...
    MT5 version: 5.0.XXXX
    Initialize result: True
    MT5 initialized successfully!
    Terminal connected: True
    Trade allowed: True

STEP 6: Run Recovery Script (if still getting timeout)
  python mt5_recovery.py
  
  This will:
  - Check MT5 process status
  - Try multiple initialization attempts
  - Verify connection
  - Provide detailed diagnostics

STEP 7: Launch System
  START_ENHANCED.bat
  
  This will:
  - Auto-detect your MT5 account
  - Update configuration
  - Start engine and dashboard
  - Show your live account data

# MAINTAINING MULTI-BROKER IMPROVEMENTS

During recovery, your multi-broker setup is preserved:

✓ Auto-detection still works (any broker)
✓ Account switching capability maintained
✓ Dashboard improvements intact
✓ All broker support preserved

The recovery process:
1. Doesn't remove auto-detection
2. Doesn't hardcode credentials again
3. Just ensures MT5 can communicate
4. Then detection works normally

# ADVANCED TROUBLESHOOTING

If standard recovery doesn't work:

OPTION A: Check MT5 Installation
  1. Verify MT5 is installed:
     dir "C:\Program Files\MetaTrader 5"
  
  2. If not found, reinstall MT5
     - Download from: https://www.exness.com (or your broker)
     - Uninstall old version first
     - Reinstall fresh

OPTION B: Check for Port/Network Issues
  1. MT5 uses TCP connections for API
  2. Your firewall might be blocking it
  3. Check Windows Defender/Firewall settings
  4. Ensure MT5 is allowed to communicate
  
  PowerShell (admin):
  Get-NetFirewallRule -DisplayName "*MetaTrader*" | Format-Table

OPTION C: Check System Resources
  If MT5 keeps freezing:
  1. Open Task Manager (Ctrl+Shift+Esc)
  2. Look at CPU and Memory for terminal64.exe
  3. If either is 100%, MT5 is struggling
  4. Close other programs
  5. Restart computer if needed

OPTION D: Reinstall MT5 (Last Resort)
  If nothing else works:
  1. Uninstall MT5 via Control Panel
  2. Delete: C:\Program Files\MetaTrader 5
  3. Delete: C:\Users\[Username]\AppData\Roaming\MetaQuotes\Terminal
  4. Restart computer
  5. Download fresh copy from broker website
  6. Install clean
  7. Log in
  8. Enable automated trading
  9. Run: START_ENHANCED.bat

# AUTOMATED RECOVERY COMMANDS

New Python Recovery Script:
  python mt5_recovery.py
  
  This does:
  - ✓ Checks if MT5 running
  - ✓ Starts it if not
  - ✓ Tries initialization 3 times
  - ✓ Handles IPC timeouts
  - ✓ Provides detailed diagnostics
  - ✓ Shows next steps

# ERROR MESSAGES EXPLAINED

"IPC timeout (4 attempts remaining)"
  → MT5 not responding, will retry
  → Usually fixes itself after restart

"Terminal: Authorization failed (-6)"
  → Automated trading not enabled
  → Tools → Options → Expert Advisors
     Check: Allow automated trading

"Failed to initialize MT5. Terminal may not be running"
  → MT5 process not found
  → Run: START_ENHANCED.bat
     It will start MT5 automatically

"Cannot connect to server"
  → Internet/network issue
  → Check your internet connection
  → Verify MT5 terminal shows "Connected"

# AFTER RECOVERY

Once recovery is complete:

1. Multi-broker auto-detection STILL WORKS
2. Run: START_ENHANCED.bat again
3. System will detect your MT5 account
4. Dashboard launches with live data

The recovery is just a "wake up" for MT5.
All improvements are preserved and functional.

# VERIFICATION

After recovery, verify everything:

1. Test detector:
   python mt5_account_detector.py
   ✓ Should show your account, broker, and balance

2. Test engine:
   python engine_launcher.py
   ✓ Should initialize and create engine_state.json

3. Test dashboard:
   START_ENHANCED.bat
   ✓ Should show LIVE status and your account data

# SUPPORT

If recovery still doesn't work:
1. Check all steps above completed
2. Verify MT5 is properly installed
3. Ensure you're using a compatible MT5 version
4. Check broker website for latest MT5 version

Remember: The improvements are still there!
This is just fixing MT5 communication.
Once fixed, everything works as designed.
"""