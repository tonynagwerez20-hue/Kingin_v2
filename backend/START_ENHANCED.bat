@echo off
REM Enhanced System Startup - Auto-fixes IPC timeout issues
REM This script will:
REM 1. Detect your active MT5 account (any broker)
REM 2. Fix IPC timeout if needed
REM 3. Update the system configuration automatically
REM 4. Start the trading engine and dashboard

color 0A
cls
echo.
echo ============================================================================
echo               HEDGE SYSTEM - ENHANCED STARTUP
echo ============================================================================
echo.

cd /d "%~dp0"

REM Check if MT5 is running
tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV > nul
if errorlevel 1 (
    echo WARNING: MetaTrader5 is not currently running
    echo.
    echo [1] Starting MetaTrader5...
    echo.
    start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
    echo Waiting for MT5 to initialize (20 seconds)...
    timeout /t 20 /nobreak
) else (
    echo ✓ MetaTrader5 is running
    echo.
)

REM Try normal initialization
echo [2] Attempting to initialize system...
python engine_launcher.py

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo ERROR: Engine initialization failed (likely IPC timeout)
    echo ============================================================================
    echo.
    echo Attempting recovery...
    echo.
    echo [RECOVERY] Running MT5 Recovery System...
    python mt5_recovery.py
    
    if errorlevel 1 (
        echo.
        echo ============================================================================
        echo RECOVERY FAILED - Manual Troubleshooting Required
        echo ============================================================================
        echo.
        echo Quick fixes:
        echo 1. Close MetaTrader5 completely
        echo 2. Wait 5 seconds
        echo 3. Reopen MetaTrader5
        echo 4. In MT5, go to: Tools ^> Options ^> Expert Advisors
        echo 5. Enable: "Allow automated trading"
        echo 6. Restart MT5
        echo 7. Run this script again
        echo.
        echo If that doesn't work:
        echo - your MT5 may be corrupted
        echo - Run: python mt5_recovery.py for more options
        echo.
        pause
        exit /b 1
    )
    
    echo.
    echo Retrying initialization after recovery...
    python engine_launcher.py
    if errorlevel 1 (
        echo Recovery completed but initialization still failed
        echo Please check MT5 settings and try again
        pause
        exit /b 1
    )
)

echo.
echo ============================================================================
echo ENGINE LAUNCHER - SYSTEM READY
echo ============================================================================
echo.
echo [3] Launching dashboard...
echo.

REM Look for the built Tauri executable or fall back to dev mode
if exist "src-tauri\target\release\its_dashboard.exe" (
    echo Starting Tauri desktop app...
    start "" "src-tauri\target\release\its_dashboard.exe"
) else if exist "src-tauri\target\debug\its_dashboard.exe" (
    echo Starting Tauri desktop app (debug mode)...
    start "" "src-tauri\target\debug\its_dashboard.exe"
) else (
    echo.
    echo Dashboard executable not found. Starting dev mode...
    echo Starting Vite development server...
    npm run dev
)

echo.
echo ============================================================================
echo ✓ SYSTEM STARTED SUCCESSFULLY
echo ============================================================================
echo.
echo Your system is now configured to use your active MT5 account
echo Dashboard is receiving live data
echo.
pause
