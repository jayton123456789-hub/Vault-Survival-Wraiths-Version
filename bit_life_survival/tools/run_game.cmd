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
) else if exist "C:\Users\nickb\AppData\Local\Programs\Python\Python311\python.exe" (
    set "BOOTSTRAP_PY=C:\Users\nickb\AppData\Local\Programs\Python\Python311\python.exe"
) else (
    python -V >nul 2>&1 && set "BOOTSTRAP_PY=python"
)

if not defined BOOTSTRAP_PY (
    echo No usable Python interpreter found.
    echo Install Python 3.11+ or update this launcher with your python.exe path.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%BOOTSTRAP_PY%" -m venv .venv
    if errorlevel 1 (
        goto :fail
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

if not exist ".venv\.deps_installed" (
    echo Installing requirements...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        goto :fail
    )
    echo ok>.venv\.deps_installed
)

echo Launching Bit Life Survival...
"%VENV_PY%" -m bit_life_survival.app.main
if errorlevel 1 goto :fail

endlocal
exit /b 0

:fail
echo.
echo Launcher failed. Press any key to close this window.
pause >nul
endlocal
exit /b 1
