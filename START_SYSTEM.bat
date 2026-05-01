@echo off
setlocal EnableDelayedExpansion
TITLE KingIn Trading System - Master Launcher

SET "ROOT_DIR=%~dp0"
SET "BACKEND_DIR=%ROOT_DIR%backend"
SET "FRONTEND_DIR=%ROOT_DIR%frontend"

echo.
echo  ==========================================================
echo     KINGIN INSTITUTIONAL TRADING SYSTEM
echo     Master Launcher v2.0
echo  ==========================================================
echo.

:: ---- Check for Python ----
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.10+
    echo          Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: ---- Check for Node ----
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  [ERROR] Node.js/npm not found. Please install Node.js 18+
    echo          Download: https://nodejs.org/
    pause
    exit /b 1
)

:: ---- Check for curl (for health check) ----
where curl >nul 2>nul
SET "HAS_CURL=%ERRORLEVEL%"

echo  [1/3] Starting Backend API (Port 8088)...
start "KingIn API" cmd /k "cd /d "%BACKEND_DIR%" && python kingin_api.py"

:: ---- Wait for backend to become ready (poll up to 30s) ----
echo  [2/3] Waiting for backend to become ready...
set /a TRIES=0

:WAIT_LOOP
timeout /t 2 /nobreak > nul
set /a TRIES+=1

if %HAS_CURL%==0 (
    curl -s --max-time 1 http://127.0.0.1:8088/api/system/status > nul 2>&1
    if !ERRORLEVEL!==0 goto BACKEND_READY
) else (
    :: Fallback: just wait 10s if curl is not available
    if %TRIES% GEQ 5 goto BACKEND_READY
)

if %TRIES% LSS 15 (
    echo       Attempt %TRIES%/15...
    goto WAIT_LOOP
)

echo  [WARN] Backend did not respond in 30s. Launching frontend anyway.
echo         Check the "KingIn API" window for error details.
goto START_FRONTEND

:BACKEND_READY
echo  [OK]  Backend is ready and responding on port 8088.

:START_FRONTEND
echo  [3/3] Starting Frontend Dashboard (Port 5173)...
start "KingIn Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev:vite"

:: Brief pause so Vite has time to start
timeout /t 4 /nobreak > nul

echo.
echo  ==========================================================
echo     SYSTEM IS RUNNING
echo.
echo     Dashboard:  http://localhost:5173
echo     API Status: http://127.0.0.1:8088/api/system/status
echo.
echo     To stop:    Close both console windows
echo  ==========================================================
echo.
echo  Press any key to close this launcher (servers continue running).
pause > nul
endlocal
