@echo off
TITLE Institutional Trading System - Universal Setup
SET "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ==========================================================
echo    HedgeEA UNIVERSAL SETUP WIZARD
echo ==========================================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and tick "Add to PATH" during installation.
    pause
    exit /b
)
echo [OK] Python found.

:: 2. Check/Create Virtual Environment
if not exist ".venv" (
    echo [INFO] Creating new virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: 3. Activate and Install Dependencies
echo [INFO] Installing dependencies...
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)

echo.
echo ==========================================================
echo    SYSTEM READY - PLATINUM DEPLOYMENT
echo ==========================================================
echo You can now run:
echo  - run_system.ps1 (Trading Engine)
echo  - START_DASHBOARD.bat (UI)
echo.
pause
