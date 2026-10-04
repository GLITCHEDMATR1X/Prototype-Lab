@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"
set "SMOKEDIR=%LOCALAPPDATA%\GLITCHED MATRIX\Afterlife of IO\smoke"
if "%LOCALAPPDATA%"=="" set "SMOKEDIR=%TEMP%\GLITCHED_MATRIX\Afterlife of IO\smoke"
if not exist "%SMOKEDIR%" mkdir "%SMOKEDIR%" >nul 2>nul

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import pygame" >nul 2>nul
  if not errorlevel 1 set "PYEXE=.venv\Scripts\python.exe"& goto RUN_SMOKE
)
py -3.12 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.12"& goto RUN_SMOKE
py -3.11 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.11"& goto RUN_SMOKE
py -3.13 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.13"& goto RUN_SMOKE
py -3.14 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.14"& goto RUN_SMOKE
python -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=python"& goto RUN_SMOKE

echo No Python runtime with pygame was found. Run INSTALL_DEPENDENCIES.bat first.
exit /b 2

:RUN_SMOKE
%PYEXE% -X faulthandler launch_afterlife.py --windowed --window-size 1920x1080 --smoke-test --test-shot "%SMOKEDIR%\windows_smoke_1920x1080.png"
if errorlevel 1 exit /b %errorlevel%
%PYEXE% -X faulthandler launch_afterlife.py --windowed --window-size 1280x720 --smoke-test --test-shot "%SMOKEDIR%\windows_smoke_1280x720.png"
exit /b %errorlevel%
