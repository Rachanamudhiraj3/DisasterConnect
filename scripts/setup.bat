@echo off
cd /d "%~dp0.."
echo Setting up the disaster alert system...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo Setup complete. Use scripts\run.bat to start (auto: online when available, offline otherwise).
pause
