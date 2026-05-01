@echo off
title ITS Installer
color 0A
echo.
echo ==========================================================
echo   INSTITUTIONAL TRADING SYSTEM - AUTO INSTALLER
echo ==========================================================
echo.
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH. Install Python 3.10+ first.
    pause
    exit /b 1
)
echo [1/4] Installing required Python packages...
python -m pip install MetaTrader5 pyzmq Pillow pywin32 fastapi uvicorn websockets --quiet
echo [2/4] Running pywin32 post-install fix...
python -m pywin32_postinstall -install >nul 2>&1
echo [3/4] Generating application icon...
python "%~dp0gen_icon.py"
echo [4/4] Creating Desktop shortcut...
python "%~dp0create_shortcut.py"
echo.
echo ==========================================================
echo   DONE. Launch "Institutional Trading System" from Desktop.
echo ==========================================================
echo.
pause
