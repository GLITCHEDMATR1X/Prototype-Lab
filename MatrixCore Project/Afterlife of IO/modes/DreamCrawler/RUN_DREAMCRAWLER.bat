@echo off
setlocal
cd /d "%~dp0"
set "DREAMCRAWLER_ALLOW_STANDALONE=1"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 main.py
) else (
  python main.py
)
if errorlevel 1 pause
endlocal
