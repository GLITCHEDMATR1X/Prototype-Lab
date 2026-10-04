@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 was not found. Install Python 3.12 or newer, then run this again.
  exit /b 1
)
py -m pip install --upgrade pygame-ce pillow
if errorlevel 1 exit /b 1
echo.
echo Visual capture runtime installed.
echo Run VERIFY_VISUAL_CHANGES.bat --initialize-baseline for the first approved build.
endlocal
