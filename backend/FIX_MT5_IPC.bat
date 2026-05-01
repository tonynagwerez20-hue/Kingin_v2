@echo off
REM MT5 IPC Timeout Fix - Force Restart and Test
echo.
echo ============================================================================
echo MT5 IPC TIMEOUT FIX - Force Restart and Test
echo ============================================================================
echo.

cd /d "%~dp0"

echo [1] Killing any existing MT5 processes...
taskkill /IM terminal64.exe /F >nul 2>&1
taskkill /IM terminal32.exe /F >nul 2>&1
taskkill /IM metaeditor64.exe /F >nul 2>&1
echo ✓ MT5 processes terminated

echo.
echo [2] Starting fresh MT5 terminal...
start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
echo ✓ MT5 started

echo.
echo [3] Waiting 25 seconds for full initialization...
timeout /t 25 /nobreak >nul

echo.
echo [4] Testing MT5 connection...
python test_mt5_simple.py

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo TEST FAILED - IPC Timeout Still Present
    echo ============================================================================
    echo.
    echo Troubleshooting steps:
    echo 1. Make sure MT5 is fully open and logged in
    echo 2. In MT5: Tools ^> Options ^> Expert Advisors
    echo 3. Enable: "Allow automated trading"
    echo 4. Restart MT5 and try again
    echo.
    echo Or run: python mt5_recovery.py
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ============================================================================
    echo SUCCESS! MT5 Connection Working
    echo ============================================================================
    echo.
    echo Now you can run: START_ENHANCED.bat
    echo.
    pause
)