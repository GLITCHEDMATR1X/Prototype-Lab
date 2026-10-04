@echo off
rem THE INDIGO GIANT - install what the game needs (Panda3D 1.10.16 and numpy) into the Python
rem that the Prototype Lab / RUN_INDIGO_GIANT.bat will use.  Safe to run again at any time.
rem A log is written to install_requirements_last.txt beside this file.
setlocal EnableExtensions
cd /d "%~dp0"
title The Indigo Giant - install requirements
set "LOG=%~dp0install_requirements_last.txt"
echo THE INDIGO GIANT - installing requirements > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

rem ---- find a 64-bit Python 3.10 - 3.13 (Panda3D 1.10.16 has wheels for these)
set "PYEXE="
for %%V in (3.12 3.11 3.13 3.10) do (
    if not defined PYEXE (
        py -%%V -c "import sys, struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
        if not errorlevel 1 set "PYEXE=py -%%V"
    )
)
if not defined PYEXE (
    python -c "import sys, struct; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE (
    echo.
    echo No suitable Python was found.
    echo Install 64-bit Python 3.12 from https://www.python.org/downloads/windows/
    echo ^(tick "Add python.exe to PATH"^), then run this file again.
    echo NO PYTHON FOUND >> "%LOG%"
    pause
    exit /b 9009
)
echo Using: %PYEXE%
%PYEXE% -c "import sys; print('Python', sys.version)" >> "%LOG%" 2>&1

rem ---- install (only what is missing or the wrong version)
echo Installing Panda3D 1.10.16 and numpy ... this can take a minute the first time.
%PYEXE% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip is missing - adding it ... >> "%LOG%"
    %PYEXE% -m ensurepip --upgrade >> "%LOG%" 2>&1
)
%PYEXE% -m pip install --disable-pip-version-check --upgrade-strategy only-if-needed -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo Retrying for this Windows user only ...
    %PYEXE% -m pip install --user --disable-pip-version-check --upgrade-strategy only-if-needed -r "%~dp0requirements.txt" >> "%LOG%" 2>&1
)

rem ---- prove it works
%PYEXE% -c "from panda3d.core import PandaSystem; import numpy, direct.showbase.ShowBase; v = PandaSystem.getVersionString(); print('Panda3D', v, '/ numpy', numpy.__version__); raise SystemExit(0 if v == '1.10.16' else 2)" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo Something did not install. Details: install_requirements_last.txt
    echo FAILED >> "%LOG%"
    pause
    exit /b 1
)
echo.
echo Ready. Panda3D 1.10.16 and numpy are installed for %PYEXE%.
echo OK >> "%LOG%"
pause
endlocal
exit /b 0
