@echo off
cd /d "%~dp0"
call .venv_v3\Scripts\activate.bat
python tests\verify_smc_signals.py
pause
