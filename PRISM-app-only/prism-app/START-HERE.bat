@echo off
REM Double-click this file. It starts the app and opens your browser.
cd /d "%~dp0prototype"
where py >nul 2>nul
if %errorlevel%==0 ( py run.py ) else ( python run.py )
echo.
echo The server has stopped. Press any key to close.
pause >nul
