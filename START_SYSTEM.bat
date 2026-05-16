@echo off
setlocal EnableDelayedExpansion
TITLE KingIn Trading System

SET "ROOT=%~dp0"
SET "BACKEND=%ROOT%backend"
SET "FRONTEND=%ROOT%frontend"

echo.
echo  =================================================
echo     KINGIN INSTITUTIONAL TRADING SYSTEM v2.0
echo  =================================================
echo.

where python >nul 2>nul || (
    echo  [ERROR] Python 3.10+ not found.
    echo          Download: https://www.python.org/downloads/
    pause & exit /b 1
)
where npm >nul 2>nul || (
    echo  [ERROR] Node.js 18+ not found.
    echo          Download: https://nodejs.org/
    pause & exit /b 1
)

echo  [1/3] Starting Backend (port 8000)...
start "KingIn Backend" cmd /k "cd /d "%BACKEND%" && python main.py"

echo  [2/3] Waiting for backend...
set TRIES=0
:WAIT
timeout /t 2 /nobreak >nul
set /a TRIES+=1
curl -s --max-time 1 http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 goto READY
if %TRIES% LSS 15 goto WAIT
echo  [WARN] Backend slow to start - continuing anyway

:READY
echo  [OK]  Backend ready.
echo  [3/3] Starting dashboard (Electron)...
cd /d "%FRONTEND%"
start npm start

echo.
echo  Press any key to exit launcher (system keeps running).
pause >nul
endlocal
