@echo off
rem Launcher for the Total Site Profile Calculator.
rem Double-click this file to open the app.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The .venv virtual environment was not found.
    echo Create it first with:  uv venv .venv --python 3.11
    echo Then install dependencies:
    echo     uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo The program exited with an error. See the message above.
    pause
)
