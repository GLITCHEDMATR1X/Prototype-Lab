@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"
set "PYTHONFAULTHANDLER=1"
set "LOGDIR=%LOCALAPPDATA%\GLITCHED MATRIX\Afterlife of IO"
if "%LOCALAPPDATA%"=="" set "LOGDIR=%~dp0saves"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
set "CONSOLELOG=%LOGDIR%\startup_console.log"
>"%CONSOLELOG%" echo Afterlife of IO current launcher - %date% %time%

rem Runtime policy established in Pass 33: prefer a project-local venv and mature Windows CPython runtimes.
rem pygame-ce officially supports 3.14, but a current Windows 11 issue report
rem matches our blank-window/direct-exit symptom on 3.14 + pygame-ce 2.5.7.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import pygame" >>"%CONSOLELOG%" 2>&1
  if not errorlevel 1 set "PYEXE=.venv\Scripts\python.exe"& goto RUN_SELECTED
)

py -3.12 -c "import pygame" >>"%CONSOLELOG%" 2>&1
if not errorlevel 1 set "PYEXE=py -3.12"& goto RUN_SELECTED
py -3.11 -c "import pygame" >>"%CONSOLELOG%" 2>&1
if not errorlevel 1 set "PYEXE=py -3.11"& goto RUN_SELECTED
py -3.13 -c "import pygame" >>"%CONSOLELOG%" 2>&1
if not errorlevel 1 set "PYEXE=py -3.13"& goto RUN_SELECTED
py -3.14 -c "import pygame" >>"%CONSOLELOG%" 2>&1
if not errorlevel 1 set "PYEXE=py -3.14"& goto RUN_SELECTED
python -c "import pygame" >>"%CONSOLELOG%" 2>&1
if not errorlevel 1 set "PYEXE=python"& goto RUN_SELECTED

echo.
echo Afterlife of IO could not find a Python installation with Pygame.
echo Run INSTALL_DEPENDENCIES.bat, then try again.
echo Diagnostic file: "%CONSOLELOG%"
echo.
pause
exit /b 2

:RUN_SELECTED
>>"%CONSOLELOG%" echo Selected interpreter: %PYEXE%
%PYEXE% -X faulthandler launch_afterlife.py --windowed %* >>"%CONSOLELOG%" 2>&1
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0

echo.
echo Afterlife of IO exited unexpectedly with code %RC%.
echo The console is being kept open so this failure cannot disappear silently.
echo.
echo Startup diagnostics:
echo   "%LOGDIR%\startup.log"
echo   "%CONSOLELOG%"
echo.
if exist "%LOGDIR%\startup.log" type "%LOGDIR%\startup.log"
echo.
echo Run RUN_RUNTIME_PROBE.bat next. It isolates pygame/SDL and game startup
echo in separate child processes so even a native SDL crash can be identified.
echo.
pause
exit /b %RC%
