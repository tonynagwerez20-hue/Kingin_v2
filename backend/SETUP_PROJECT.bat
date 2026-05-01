@echo off
TITLE KingIn Institutional Trading System - SETUP
SET "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ==========================================================
echo    KingIn PROFESSIONAL SETUP ^& INSTALLATION
echo ==========================================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and tick "Add to PATH".
    pause
    exit /b
)
echo [OK] Python detected.

:: 2. Install Python Dependencies (Global)
echo [INFO] Installing Python libraries globally...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --user
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python dependency installation failed.
    echo Try running as Administrator if permissions are denied.
    pause
    exit /b
)
echo [OK] Python libraries installed.

:: 4. Initialize .env if missing
if not exist ".env" (
    echo [INFO] Initializing .env file...
    echo KINGIN_USER_PASSWORD=kingin123 > .env
    echo KINGIN_JWT_SECRET=%RANDOM%%RANDOM% >> .env
    echo [OK] .env initialized with default password 'kingin123'.
)

:: 5. Create system directories
echo [INFO] Creating system directories...
if not exist "storage\logs"        mkdir "storage\logs"
if not exist "storage\news_cache"  mkdir "storage\news_cache"
if not exist "data"                mkdir "data"
if not exist "models"              mkdir "models"
echo [OK] Folders ready.

:: 6. Check for Node.js
node --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Node.js detected.
    echo [INFO] Installing Node dependencies...
    call npm install
    cd kingin-vite
    call npm install
    cd ..
) else (
    echo [WARN] Node.js not found. Cannot build desktop app dashboard.
)

echo.
echo ==========================================================
echo    SETUP COMPLETE
echo ==========================================================
echo 1. Set your custom password in .env file.
echo 2. Map your symbols in Engine/data_feed/symbol_map.json.
echo 3. Run BUILD_DESKTOP_APP.bat to generate the installer.
echo ==========================================================
pause