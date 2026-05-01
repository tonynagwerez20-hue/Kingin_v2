@echo off
SETLOCAL EnableDelayedExpansion
TITLE Institutional Gold System - DIRECT TOGGLE
COLOR 0B

:: Get project root
SET "PROJECT_DIR=%~dp0"
CD /D "%PROJECT_DIR%"

echo.
echo ==========================================================
echo    NEXUS TERMINAL - UNIVERSAL CONTROL SWITCH
echo ==========================================================
echo.

:: Detect Status
if exist "system.lock" (
    echo [!] STATUS: SYSTEM ACTIVE
    echo [>] ACTION: COMMENCE GRACEFUL SHUTDOWN...
) else (
    echo [ ] STATUS: SYSTEM OFFLINE
    echo [>] ACTION: LAUNCHING PROFESSIONAL INFRASTRUCTURE...
)

echo.
echo ----------------------------------------------------------
echo Press ANY KEY to Toggle System or Ctrl+C to Cancel
pause > nul

:: Execute Toggle
SET "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
if not exist "!PYTHON_EXE!" (
    SET "PYTHON_EXE=python"
)

"!PYTHON_EXE!" "!PROJECT_DIR!start_system.py"

echo.
echo [DONE] Master switch operation complete.
echo ----------------------------------------------------------
timeout /t 3
exit
