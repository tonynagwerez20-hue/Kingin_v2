@echo off
setlocal
TITLE KingIn Trading System - Production Build

SET "ROOT_DIR=%~dp0"
SET "FRONTEND_DIR=%ROOT_DIR%frontend"

echo ==========================================================
echo    KINGIN TRADING SYSTEM - PRODUCTION BUILD
echo ==========================================================
echo.

:: 1. Check for Node.js
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js/npm not found. Please install Node.js 18+
    pause
    exit /b 1
)

cd /d "%FRONTEND_DIR%"

echo [1/3] Installing frontend dependencies...
call npm install
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building React production bundle...
call npm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Vite build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Packaging Electron Application...
echo This will create a portable Windows executable in frontend\dist_electron
call npm run electron:build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Electron build failed.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo    BUILD COMPLETE!
echo    Your executable is located in:
echo    %FRONTEND_DIR%\dist_electron\
echo ==========================================================
echo.
pause
endlocal
