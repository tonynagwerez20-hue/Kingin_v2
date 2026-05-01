@echo off
TITLE Institutional Trading System - PORTABLE SETUP
SET "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

echo ==========================================================
echo    HedgeEA PROFESSIONAL SETUP ^& INSTALLATION
echo ==========================================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10 and tick "Add to PATH".
    pause
    exit /b
)
echo [OK] Python detected.
   
   :: 2. Install/Update Core Dependencies
   echo [INFO] Installing required libraries into Global Python...
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   
   if %ERRORLEVEL% neq 0 (
       echo [ERROR] Dependency installation failed. Check internet or Python permissions.
       pause
       exit /b
   )
echo [OK] Libraries installed successfully.

:: 3. Setup Folders (including news cache directory)
echo [INFO] Creating system directories...
if not exist "storage\logs"        mkdir "storage\logs"
if not exist "storage\news_cache"  mkdir "storage\news_cache"
if not exist "storage\risk_state"  mkdir "storage\risk_state"
if not exist "data"                mkdir "data"
echo [OK] Folders ready.

:: 4. Optional: Build React Dashboard (if Node.js is present)
   echo.
   echo [INFO] Checking for Node.js (optional - for React dashboard development)...
   node --version >nul 2>&1
   if %ERRORLEVEL% equ 0 (
       echo [OK] Node.js detected.
       if exist "dashboard-react\package.json" (
           echo [INFO] Installing React dashboard dependencies...
           cd dashboard-react
           call npm install --silent
           echo [INFO] Building React dashboard...
           call npm run build --silent
           cd ..
           echo [OK] React dashboard built at dashboard-react\build\
           echo        (The system will serve the built dashboard from dashboard\ if available)
       ) else (
           echo [INFO] dashboard-react\package.json not found. Skipping React build.
       )
   ) else (
       echo [INFO] Node.js not found. React dashboard development features skipped.
       echo        To enable React dev mode: install Node.js 18+ and re-run SETUP_PROJECT.bat
   )

:: 5. Final summary
echo.
echo ==========================================================
echo    SETUP COMPLETE
echo ==========================================================
echo 1. Open MetaTrader 5 and log in.
echo 2. Run START_ALL.bat to launch the system.
echo 3. React dashboard: http://localhost:3000  (if enabled)
echo.
echo NOTE: Global Python 3.10 is the recommended stable path.
echo       Avoid virtual environments if you experience crashes.
echo ==========================================================
pause
