@echo off
setlocal
TITLE KingIn Trading System - Master Launcher

SET "ROOT_DIR=%~dp0"
SET "BACKEND_DIR=%ROOT_DIR%backend"
SET "FRONTEND_DIR=%ROOT_DIR%frontend"

echo ==========================================================
echo    KINGIN INSTITUTIONAL TRADING SYSTEM
echo ==========================================================
echo.

:: Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Check for Node
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js/npm not found. Please install Node.js 18+
    pause
    exit /b 1
)

echo [1/2] Starting Backend API (Port 8088)...
start "KingIn API" cmd /k "cd /d ""%BACKEND_DIR%"" && python kingin_api.py"

timeout /t 3 /nobreak > nul

echo [2/2] Starting Frontend Dashboard (Port 5000)...
start "KingIn Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

timeout /t 5 /nobreak > nul

echo.
echo System is starting...
echo Dashboard: http://localhost:5000
echo API Status: http://127.0.0.1:8088/api/system/status
echo.
echo Press any key to exit this launcher (servers will remain running).
pause > nul
endlocal
