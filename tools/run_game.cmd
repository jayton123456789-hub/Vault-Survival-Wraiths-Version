@echo off
setlocal

cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with py -3.11...
    py -3.11 -m venv .venv 2>nul
    if errorlevel 1 (
        echo Python 3.11 launcher not available, trying py -3...
        py -3 -m venv .venv
        if errorlevel 1 (
            echo Failed to create virtual environment.
            exit /b 1
        )
    )
)

if not exist ".venv\.deps_installed" (
    echo Installing requirements...
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        exit /b 1
    )
    echo ok>.venv\.deps_installed
)

echo Starting Bit Life Survival...
.venv\Scripts\python -m bit_life_survival.app.main

endlocal
