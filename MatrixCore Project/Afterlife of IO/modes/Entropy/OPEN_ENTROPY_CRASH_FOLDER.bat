@echo off
setlocal
set "CRASHDIR=%LOCALAPPDATA%\GLITCHED MATRIX\Entropy\crashes"
if not exist "%CRASHDIR%" mkdir "%CRASHDIR%" >nul 2>&1
start "" "%CRASHDIR%"
endlocal
