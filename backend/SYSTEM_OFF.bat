@echo off
setlocal enabledelayedexpansion
TITLE Institutional Trading System - SHUTDOWN
SET "PROJECT_DIR=%~dp0"
if defined ITS_PYTHON_EXE (
    SET "PYTHON_EXE=%ITS_PYTHON_EXE%"
) else (
    SET "PYTHON_EXE=python"
)

echo ==========================================================
echo    INSTITUTIONAL TRADING SYSTEM - SHUTDOWN
echo ==========================================================
echo.

:: 1. Force Master Switch OFF
echo [1/3] Deactivating Master Switch...
"%PYTHON_EXE%" "%PROJECT_DIR%toggle_system.py" OFF
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Could not set Master Switch OFF. Continuing shutdown...
)

:: 2. Kill Data Feed Server on Port 8000
echo [2/3] Stopping Data Feed Server on Port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo [SYSTEM] Terminating PID %%a on Port 8000...
    taskkill /PID %%a /F >nul 2>&1
)

:: 3. Kill named console windows launched by START_ALL.bat
echo [3/3] Closing Engine and Dashboard processes...
taskkill /FI "WINDOWTITLE eq DTC Server*"       /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Dashboard*"        /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq React Dashboard*"  /F >nul 2>&1

:: Kill modular_bootstrapper if still running as a python process
wmic process where "commandline like '%%modular_bootstrapper%%'" delete >nul 2>&1

echo.
echo [OK] System shutdown complete.
timeout /t 3
