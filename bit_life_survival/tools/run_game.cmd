@echo off
setlocal

set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

set "BOOTSTRAP_PY="
if exist ".venv\Scripts\python.exe" (
    set "BOOTSTRAP_PY=.venv\Scripts\python.exe"
) else if exist "C:\Users\nickb\AppData\Local\Programs\Python\Python313\python.exe" (
    set "BOOTSTRAP_PY=C:\Users\nickb\AppData\Local\Programs\Python\Python313\python.exe"
) else if exist "C:\Users\nickb\AppData\Local\Programs\Python\Python312\python.exe" (
    set "BOOTSTRAP_PY=C:\Users\nickb\AppData\Local\Programs\Python\Python312\python.exe"
) else (
    set "BOOTSTRAP_PY=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%BOOTSTRAP_PY%" -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

if not exist ".venv\.deps_installed" (
    echo Installing requirements...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed.
        exit /b 1
    )
    echo ok>.venv\.deps_installed
)

echo Launching Bit Life Survival...
"%VENV_PY%" -m bit_life_survival.app.main

endlocal
