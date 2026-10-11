@echo off
cd /d "%~dp0.."
call venv\Scripts\activate.bat
echo Starting the monitoring loop -- AUTO mode (online when available, offline otherwise)...
python main.py --mode auto
pause
