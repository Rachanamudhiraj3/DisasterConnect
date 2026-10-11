@echo off
cd /d "%~dp0.."
call venv\Scripts\activate.bat
echo Starting the monitoring loop -- OFFLINE mode (forced, for testing)...
python main.py --mode offline
pause
