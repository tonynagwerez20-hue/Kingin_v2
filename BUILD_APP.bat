@echo off
setlocal
TITLE KingIn - Production Build
SET "ROOT=%~dp0"
SET "BACKEND=%ROOT%backend"
SET "FRONTEND=%ROOT%frontend"

echo =======================================================
echo    KINGIN TRADING SYSTEM v2.0 - PRODUCTION BUILD
echo =======================================================
echo.

:: Check tools
where python >nul 2>nul || (echo [ERROR] Python not found & pause & exit /b 1)
where npm    >nul 2>nul || (echo [ERROR] Node not found    & pause & exit /b 1)
where pyinstaller >nul 2>nul || (
    echo [SETUP] Installing pyinstaller...
    pip install pyinstaller --quiet
)

echo [1/4] Building Python backend...
python build_app.py
if %errorlevel% neq 0 (echo [ERROR] Backend build failed & pause & exit /b 1)

echo.
echo [2/4] Installing frontend packages...
cd /d "%FRONTEND%"
call npm install
if %errorlevel% neq 0 (echo [ERROR] npm install failed & pause & exit /b 1)

echo.
echo [3/4] Packaging Electron app...
call npm run dist
if %errorlevel% neq 0 (echo [ERROR] Electron build failed & pause & exit /b 1)

echo.
echo [4/4] Done.
echo.
echo =======================================================
echo    BUILD COMPLETE
echo    Installer: %FRONTEND%\installer_output\KingIn Trading System Setup 2.0.0.exe
echo =======================================================
echo.
pause
endlocal
