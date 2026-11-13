@echo off
REM PRISM launcher for Windows. Double-click this file.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py run.py %*
) else (
    python run.py %*
)
echo.
echo The server has stopped. Press any key to close this window.
pause >nul
