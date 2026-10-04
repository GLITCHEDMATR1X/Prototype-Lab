@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"
set "PYTHONFAULTHANDLER=1"

echo Afterlife of IO - Current Runtime Compatibility Probe
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import pygame" >nul 2>nul
  if not errorlevel 1 (
    set "PYEXE=.venv\Scripts\python.exe"
    goto RUN_PROBE
  )
)

py -3.12 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.12"& goto RUN_PROBE
py -3.11 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.11"& goto RUN_PROBE
py -3.13 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.13"& goto RUN_PROBE
py -3.14 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=py -3.14"& goto RUN_PROBE
python -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PYEXE=python"& goto RUN_PROBE

echo No Python runtime with pygame was found.
echo Run INSTALL_DEPENDENCIES.bat first.
echo.
pause
exit /b 2

:RUN_PROBE
echo Using: %PYEXE%
echo.
%PYEXE% -X faulthandler tools\runtime_probe.py
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Runtime probe completed without a blocking failure.
) else (
  echo Runtime probe found a blocking failure. Exit code %RC%.
)
echo.
echo The report is also written to:
echo   %%LOCALAPPDATA%%\GLITCHED MATRIX\Afterlife of IO\runtime_probe_report.txt
echo.
pause
exit /b %RC%
