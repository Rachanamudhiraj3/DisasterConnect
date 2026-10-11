@echo off
cd /d "%~dp0.."
call venv\Scripts\activate.bat
echo Starting the local web app...
echo Open http://localhost:5000 in your browser once this says "Running on".
python -m backend.server
pause
