@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "FRONTEND_DIR=%PROJECT_DIR%kingin-vite"

if defined ITS_PYTHON_EXE (
    set "PYTHON_EXE=%ITS_PYTHON_EXE%"
) else (
    set "PYTHON_EXE=python"
)

cd /d "%PROJECT_DIR%"

echo Launching KingIn local desktop dashboard...
echo.

where "%PYTHON_EXE%" >nul 2>nul
if %errorlevel% neq 0 (
    python --version >nul 2>nul
    if %errorlevel% neq 0 (
        echo ERROR: Python is not installed or not in PATH.
        echo Install Python 3.10 or newer and rerun SETUP_PROJECT.bat.
        pause
        exit /b 1
    )
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: npm not found. Install Node.js 18 or newer.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: React dashboard package not found at %FRONTEND_DIR%.
    pause
    exit /b 1
)

echo Starting API server on http://127.0.0.1:8080 ...
start "KingIn API" cmd /k "cd /d ""%PROJECT_DIR%"" && ""%PYTHON_EXE%"" kingin_api.py"

echo Starting dashboard on http://localhost:5000 ...
start "KingIn Dashboard" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm install --prefer-offline && npm run dev"

timeout /t 5 >nul
start "" "http://localhost:5000"

echo.
echo KingIn is starting in separate windows.
echo Close those windows to stop the local dashboard and API.

endlocal
pause
