@echo off
setlocal enabledelayedexpansion
TITLE Institutional Trading System - ONE-CLICK START
SET "PROJECT_DIR=%~dp0"
if defined ITS_PYTHON_EXE (
    SET "PYTHON_EXE=%ITS_PYTHON_EXE%"
) else (
    REM Auto-detect Python executable: prefer ITS_PYTHON_EXE, then PATH, then py launcher, fallback to 'python'
    SET "PYTHON_EXE="
    if defined ITS_PYTHON_EXE (
        SET "PYTHON_EXE=%ITS_PYTHON_EXE%"
    ) else (
        for /f "delims=" %%P in ('where python 2^>nul') do @if not defined PYTHON_EXE set "PYTHON_EXE=%%~fP"
        if not defined PYTHON_EXE (
            for /f "delims=" %%P in ('where py 2^>nul') do @if not defined PYTHON_EXE set "PYTHON_EXE=%%~fP"
        )
        if not defined PYTHON_EXE (
            SET "PYTHON_EXE=python"
        )
    )
)
SET "STREAMLIT_EXE=streamlit"
SET "DASHBOARD_PY=%PROJECT_DIR%dashboard\dashboard_app.py"

echo ==========================================================
echo    INSTITUTIONAL TRADING SYSTEM - ULTIMATE START
echo ==========================================================
echo.

:: 1. Force Master Switch ON
echo [1/4] Activating Master Switch...
"%PYTHON_EXE%" "%PROJECT_DIR%toggle_system.py" ON
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to set Master Switch.
    pause
    exit /b
)

:: Ensure news cache directory exists (required by NewsEventLayer)
if not exist "%PROJECT_DIR%storage\news_cache" mkdir "%PROJECT_DIR%storage\news_cache"

:: Pre-emptive: Kill any process on Port 8000 (Data Server)
echo [SYSTEM] Checking for existing Data Server on Port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo [SYSTEM] Found ghost process %%a on Port 8000. Terminating...
    taskkill /PID %%a /F >nul 2>&1
)

:: 2. Launch Data Feed Server in Background
echo [2/4] Launching Data Feed Server...
start "DTC Server" cmd /k ""%PYTHON_EXE%" "%PROJECT_DIR%data_feed\server.py""
echo Waiting 5s for server initialization...
timeout /t 5 >nul

:: 3. Dashboard selection logic
echo [3/4] Checking Dashboard Configuration...
set "LAUNCH_STREAMLIT=false"
set "LAUNCH_REACT=false"

:: Check if Streamlit dashboard is enabled
findstr /C:"enable_streamlit_dashboard" "%PROJECT_DIR%config\trading_params_lite.json" | findstr /I "true" >nul
if %ERRORLEVEL% equ 0 set "LAUNCH_STREAMLIT=true"

:: Check if React dashboard is enabled
findstr /C:"enable_react_dashboard" "%PROJECT_DIR%config\trading_params_lite.json" | findstr /I "true" >nul
if %ERRORLEVEL% equ 0 set "LAUNCH_REACT=true"

if "!LAUNCH_REACT!"=="true" (
    echo [3/4] Launching React Dashboard on http://localhost:3000 ...
    echo [INFO] Engine API will auto-start on http://localhost:3001

    :: The dashboard is a single index.html served statically via Python http.server.
    :: No npm or Node required. Check all likely folder locations in priority order.
    set "REACT_DIR="
    if exist "!PROJECT_DIR!Dashboard\index.html"  set "REACT_DIR=!PROJECT_DIR!Dashboard"
    if exist "!PROJECT_DIR!dashboard\index.html"  if "!REACT_DIR!"=="" set "REACT_DIR=!PROJECT_DIR!dashboard"
    if exist "!PROJECT_DIR!index.html"            if "!REACT_DIR!"=="" set "REACT_DIR=!PROJECT_DIR!"

    if "!REACT_DIR!"=="" (
        echo [ERROR] Dashboard index.html not found. Checked:
        echo          !PROJECT_DIR!Dashboard\index.html
        echo          !PROJECT_DIR!dashboard\index.html
        echo          !PROJECT_DIR!index.html
        echo [FIX]    Place index.html in !PROJECT_DIR!Dashboard\ and restart.
    ) else (
        echo [OK] Serving dashboard from: !REACT_DIR!
        start "React Dashboard" cmd /k "cd /d "!REACT_DIR!" && "!PYTHON_EXE!" -m http.server 3000"
        echo [OK] Open http://localhost:3000 in your browser after engine starts.
    )

) else if "!LAUNCH_STREAMLIT!"=="true" (
    echo [3/4] Launching Streamlit Dashboard...
    where streamlit >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        start "Dashboard" cmd /c "cd /d "!PROJECT_DIR!" && "!STREAMLIT_EXE!" run "!DASHBOARD_PY!""
    ) else (
        echo [WARNING] Streamlit not found. Dashboard will not start.
    )
) else (
    echo [INFO] All dashboards DISABLED in config. Skipping.
)

:: 4. Run Modular Strategy Pipeline in Foreground
echo [4/4] Starting Trading Engine...
echo.
set "PYTHONPATH=!PROJECT_DIR!"
"%PYTHON_EXE%" -m Engine.modular_bootstrapper

echo.
echo System stopped.
pause
