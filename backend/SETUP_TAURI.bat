@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "FRONTEND_DIR=%PROJECT_DIR%kingin-vite"

cd /d "%PROJECT_DIR%"

echo KingIn local desktop setup
echo.
echo This master branch does not contain a Tauri native-app project.
echo It runs as a local Windows desktop/browser dashboard backed by the Python API.
echo.

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found. Install Node.js 18 or newer from https://nodejs.org
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: npm not found. Reinstall Node.js with npm enabled.
    pause
    exit /b 1
)

python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install Python 3.10 or newer and tick Add Python to PATH.
    pause
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Python dependency installation failed.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: React dashboard package not found at %FRONTEND_DIR%.
    pause
    exit /b 1
)

cd /d "%FRONTEND_DIR%"
echo Installing dashboard dependencies...
if exist package-lock.json (
    call npm ci
) else (
    call npm install
)
if %errorlevel% neq 0 (
    echo ERROR: Dashboard dependency installation failed.
    pause
    exit /b 1
)

call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Dashboard build failed.
    pause
    exit /b 1
)

echo.
echo Setup complete.
echo Run LAUNCH_DESKTOP_APP.bat to start the local desktop dashboard.

endlocal
pause
