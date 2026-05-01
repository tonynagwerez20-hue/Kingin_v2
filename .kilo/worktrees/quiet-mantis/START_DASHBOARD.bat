@echo off
TITLE Institutional Trading System - Dashboard
SET "PROJECT_DIR=%~dp0"
SET "STREAMLIT_EXE=%PROJECT_DIR%.venv_v2\Scripts\streamlit.exe"
SET "APP_PY=%PROJECT_DIR%dashboard\dashboard_app.py"

echo ==========================================================
echo    INSTITUTIONAL TRADING SYSTEM - DASHBOARD
echo ==========================================================
echo Starting Premium Dashboard...
echo Dashboard Path: %APP_PY%
echo.

:: Check if streamlit exists
if not exist "%STREAMLIT_EXE%" (
    echo [ERROR] Virtual environment or Streamlit not found at %STREAMLIT_EXE%
    echo Please ensure the venv is created and dependencies are installed.
    pause
    exit /b
)

:: Run the dashboard
cd /d "%PROJECT_DIR%"
streamlit run "%APP_PY%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dashboard failed to start or was closed unexpectedly.
    pause
)
