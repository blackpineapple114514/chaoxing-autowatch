@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   Chaoxing AutoWatch - starting web app ...
echo.
python app.py
echo.
echo   App stopped. Press any key to close.
pause >nul
