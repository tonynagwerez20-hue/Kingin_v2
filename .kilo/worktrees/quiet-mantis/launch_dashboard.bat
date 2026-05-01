@echo off
REM Auto-launch script for Hedge Trading System Dashboard
REM This batch file starts both the backend server and React dashboard

echo === Hedge Trading System - Auto Launch ===
echo.

REM Start FastAPI server in background
echo [1/3] Starting FastAPI backend server...
start "Hedge API Server" cmd /k "cd /d %~dp0 && .\.venv_v2\Scripts\python.exe data_feed\server.py"
timeout /t 5 /nobreak > nul

REM Start React development server
echo [2/3] Starting React dashboard...
start "Hedge Dashboard" cmd /k "cd /d %~dp0dashboard-react && ..\.venv_v2\Scripts\python.exe -m http.server 3000"
timeout /t 10 /nobreak > nul

REM Open dashboard in default browser
echo [3/3] Opening dashboard in browser...
start http://localhost:3000

echo.
echo Dashboard launched successfully!
echo   Dashboard URL: http://localhost:3000
echo   API Server: http://localhost:8000
echo.
echo Press any key to close this window (servers will continue running)...
pause > nul
