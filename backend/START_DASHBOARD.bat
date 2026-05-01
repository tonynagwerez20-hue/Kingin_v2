@echo off
TITLE Institutional Trading System - Dashboard
SET "PROJECT_DIR=%~dp0"
SET "APP_PY=%PROJECT_DIR%dashboard\dashboard_app.py"

echo ==========================================================
echo    INSTITUTIONAL TRADING SYSTEM - DASHBOARD
echo ==========================================================
echo Starting Premium Dashboard...
echo Dashboard Path: %APP_PY%
echo.

where streamlit >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Streamlit was not found in PATH.
    echo Run SETUP_PROJECT.bat first to install dependencies.
    pause
    exit /b 1
)

if not exist "%APP_PY%" (
    echo [ERROR] Dashboard file not found: %APP_PY%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
streamlit run "%APP_PY%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dashboard failed to start or was closed unexpectedly.
    pause
)
