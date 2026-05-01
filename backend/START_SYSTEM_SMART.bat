@echo off
REM Intelligent System Startup - Auto-detects any MT5 account on any broker
REM This script will:
REM 1. Detect your active MT5 account (Exness, ICMarkets, etc.)
REM 2. Update the system configuration automatically
REM 3. Start the trading engine and dashboard

color 0A
cls
echo.
echo ============================================================================
echo               HEDGE SYSTEM - INTELLIGENT STARTUP
echo ============================================================================
echo.
echo NOTE: Make sure MetaTrader5 is open and logged in with your account
echo.
echo [1] Auto-detecting MT5 account...
echo.

cd /d "%~dp0"

REM Try to detect and initialize
python engine_launcher.py

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo ERROR: Engine initialization failed
    echo ============================================================================
    echo.
    echo Troubleshooting:
    echo 1. Is MetaTrader5 open and logged in?
    echo 2. Does automated trading have the right permissions (Tools ^> Options ^> Expert Advisors)?
    echo 3. Is your account properly connected?
    echo.
    echo If problems persist, run: python mt5_account_detector.py
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo ENGINE LAUNCHER - SETTING UP YOUR ACCOUNT
echo ============================================================================
echo.
echo [2] Launching dashboard...
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
echo Your system is now configured to use your active MT5 account:
echo - Broker: Auto-detected
echo - Account: Auto-detected
echo - Dashboard: Live data streaming
echo.
echo To stop the system, close this window and the dashboard application.
echo.
pause
