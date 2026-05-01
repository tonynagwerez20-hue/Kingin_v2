@echo off
setlocal

SET "PROJECT_DIR=%~dp0"
SET "FRONTEND_DIR=%PROJECT_DIR%kingin-vite"

if defined ITS_PYTHON_EXE (
    SET "PYTHON_EXE=%ITS_PYTHON_EXE%"
) else (
    SET "PYTHON_EXE=python"
)

echo === KingIn Dashboard - Auto Launch ===
echo.

if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Dashboard package not found at %FRONTEND_DIR%.
    pause
    exit /b 1
)

echo [1/3] Starting KingIn API server...
start "KingIn API Server" cmd /k "cd /d ""%PROJECT_DIR%"" && ""%PYTHON_EXE%"" kingin_api.py"
timeout /t 5 /nobreak > nul

echo [2/3] Starting React dashboard...
start "KingIn Dashboard" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm install --prefer-offline && npm run dev"
timeout /t 8 /nobreak > nul

echo [3/3] Opening dashboard in browser...
start "" "http://localhost:5000"

echo.
echo Dashboard launched.
echo   Dashboard URL: http://localhost:5000
echo   API Server: http://127.0.0.1:8080
echo.
echo Press any key to close this launcher window. Servers continue in their own windows.
pause > nul

endlocal
