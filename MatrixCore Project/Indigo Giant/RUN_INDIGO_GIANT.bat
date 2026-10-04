@echo off
setlocal
cd /d "%~dp0"
title The Indigo Giant

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYEXE=py -3.12"
)
if not defined PYEXE (
    where python >nul 2>nul
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
    echo ERROR: No usable Python was found.
    pause
    exit /b 9009
)

%PYEXE% -c "import panda3d, numpy" >nul 2>nul
if errorlevel 1 (
    echo Installing requirements ^(panda3d 1.10.16, numpy^)...
    %PYEXE% -m pip install -r "%~dp0requirements.txt"
)

rem Add --fps to show the frame counter at launch (F3 toggles it in game).
%PYEXE% "%~dp0main.py" %*
if errorlevel 1 (
    echo.
    echo The game stopped with an error. Run .dev\RUN_DIAGNOSTIC.bat for a full log.
    pause
)
endlocal
