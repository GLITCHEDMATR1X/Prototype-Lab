@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_CMD="
py -3 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD python -c "import sys" >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo ERROR: Python 3 was not found.
    echo This is the source build. Your itch launcher should bundle the runtime.
    pause
    exit /b 2
)

%PYTHON_CMD% -c "import pygame; assert pygame.version.ver.startswith('2.5.')" >nul 2>nul
if errorlevel 1 (
    echo ERROR: pygame-ce 2.5.x is not available to this Python runtime.
    echo Install source requirements with:
    echo     %PYTHON_CMD% -m pip install -r requirements.txt
    echo Your final itch launcher should bundle the dependency instead.
    pause
    exit /b 2
)

%PYTHON_CMD% main.py %*
if errorlevel 1 pause
