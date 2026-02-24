@echo off
setlocal

cd /d "%~dp0\.."

set "BOOTSTRAP_PY="
set "BOOTSTRAP_ARGS="
if exist ".venv\Scripts\python.exe" (
    set "BOOTSTRAP_PY=.venv\Scripts\python.exe"
)
if not defined BOOTSTRAP_PY (
    py -3.11 -V >nul 2>&1 && set "BOOTSTRAP_PY=py" && set "BOOTSTRAP_ARGS=-3.11"
)
if not defined BOOTSTRAP_PY (
    py -V >nul 2>&1 && set "BOOTSTRAP_PY=py"
)
if not defined BOOTSTRAP_PY (
    python -V >nul 2>&1 && set "BOOTSTRAP_PY=python"
)
if not defined BOOTSTRAP_PY (
    echo No usable Python interpreter found.
    echo Install Python 3.11+ or update tools\run_game.cmd with your python.exe path.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%BOOTSTRAP_PY%" %BOOTSTRAP_ARGS% -m venv .venv
    if errorlevel 1 goto :fail
)

if not exist ".venv\.deps_installed" (
    echo Installing requirements...
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt
    if errorlevel 1 (
        goto :fail
    )
    echo ok>.venv\.deps_installed
)

echo Starting Bit Life Survival...
.venv\Scripts\python -m bit_life_survival.app.main
if errorlevel 1 goto :fail

endlocal
exit /b 0

:fail
echo.
echo Launcher failed. Press any key to close this window.
pause >nul
endlocal
exit /b 1
