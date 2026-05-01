@echo off
echo ============================================
echo  Installing pyzmq for HedgeEA Signal Bridge
echo ============================================
echo.

REM Try pip directly first
pip install pyzmq --break-system-packages 2>nul
if %ERRORLEVEL% == 0 (
    echo [OK] pyzmq installed via pip
    goto :verify
)

REM Try pip3
pip3 install pyzmq 2>nul
if %ERRORLEVEL% == 0 (
    echo [OK] pyzmq installed via pip3
    goto :verify
)

REM Try python -m pip
python -m pip install pyzmq 2>nul
if %ERRORLEVEL% == 0 (
    echo [OK] pyzmq installed via python -m pip
    goto :verify
)

REM Try python3 -m pip
python3 -m pip install pyzmq 2>nul
if %ERRORLEVEL% == 0 (
    echo [OK] pyzmq installed via python3 -m pip
    goto :verify
)

REM Try with the python that runs the engine
echo Trying to find python used by engine...
where python >> python_path.txt 2>nul
for /f "tokens=*" %%i in (python_path.txt) do (
    "%%i" -m pip install pyzmq
    if %ERRORLEVEL% == 0 (
        echo [OK] pyzmq installed via %%i
        del python_path.txt
        goto :verify
    )
)
del python_path.txt 2>nul

echo.
echo [ERROR] Could not install pyzmq automatically.
echo Please run manually:
echo   python -m pip install pyzmq
echo.
pause
exit /b 1

:verify
echo.
echo Verifying installation...
python -c "import zmq; print('[OK] pyzmq version:', zmq.__version__)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    python3 -c "import zmq; print('[OK] pyzmq version:', zmq.__version__)" 2>nul
)
echo.
echo ============================================
echo  Done! Restart the trading engine now.
echo ============================================
pause
