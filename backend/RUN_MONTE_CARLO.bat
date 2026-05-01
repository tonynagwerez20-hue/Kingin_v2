@echo off
echo ========================================================
echo   Monte Carlo Simulation Runner - XAUUSD Strategy
echo ========================================================
echo.
echo Initializing environment...
if not exist .venv (
    echo Error: .venv not found. Please ensure the virtual environment is set up.
    pause
    exit /b 1
)

echo Starting simulation engine...
echo --------------------------------------------------------
.venv\Scripts\python.exe Engine\monte_carlo_engine.py
echo --------------------------------------------------------
echo.
echo Simulation Complete. Opening report...
if exist data\mc_report_summary.md (
    start data\mc_report_summary.md
) else (
    echo Error: Report not found in data\mc_report_summary.md
)
echo.
pause
