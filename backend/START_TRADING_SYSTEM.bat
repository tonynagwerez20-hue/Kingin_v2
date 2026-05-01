@echo off
TITLE Institutional Trading System - Start Console
SET "PROJECT_DIR=e:\s.y.s.t.e.m"
SET "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"

echo ==========================================================
echo    INSTITUTIONAL TRADING SYSTEM - v5.2.0 (RC)
echo ==========================================================
echo Starting system components...
echo Current Directory: %PROJECT_DIR%
echo Python Path: %PYTHON_EXE%
echo.

:: Check if python exists
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at %PYTHON_EXE%
    echo Please ensure the venv is created correctly.
    pause
    exit /b
)

:: Run the system
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" start_system.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [CRITICAL] System exited with error code %ERRORLEVEL%
    pause
) else (
    echo.
    echo System shut down normally.
    pause
)
