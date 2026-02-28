@echo off
setlocal

cd /d "%~dp0"
call "%~dp0tools\run_game.cmd"
if errorlevel 1 goto :fail

endlocal
exit /b 0

:fail
echo.
echo Failed to launch Bit Life Survival.
echo Press any key to close.
pause >nul
endlocal
exit /b 1
