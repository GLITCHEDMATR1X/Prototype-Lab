@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Afterlife of IO - compatible Python environment installer
echo Recommended Windows runtime: CPython 3.12 x64, then 3.11.
echo.

if exist ".venv\Scripts\python.exe" goto INSTALL

py -3.12 -c "import sys; print(sys.executable)" >nul 2>nul
if not errorlevel 1 set "BASEPY=py -3.12"& goto MAKE_VENV
py -3.11 -c "import sys; print(sys.executable)" >nul 2>nul
if not errorlevel 1 set "BASEPY=py -3.11"& goto MAKE_VENV
py -3.13 -c "import sys; print(sys.executable)" >nul 2>nul
if not errorlevel 1 set "BASEPY=py -3.13"& goto MAKE_VENV
py -3.14 -c "import sys; print(sys.executable)" >nul 2>nul
if not errorlevel 1 set "BASEPY=py -3.14"& goto MAKE_VENV
python -c "import sys; print(sys.executable)" >nul 2>nul
if not errorlevel 1 set "BASEPY=python"& goto MAKE_VENV

echo No supported Python was found.
echo Install 64-bit Python 3.12 from python.org, then rerun this file.
echo.
pause
exit /b 1

:MAKE_VENV
echo Creating isolated .venv with %BASEPY% ...
%BASEPY% -m venv .venv
if errorlevel 1 (
  echo Failed to create .venv.
  pause
  exit /b 1
)

:INSTALL
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto FAIL
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto FAIL

echo.
".venv\Scripts\python.exe" -c "import sys, pygame; print('Python:', sys.version); print('pygame-ce:', pygame.version.ver); print('SDL:', pygame.get_sdl_version())"
echo.
echo Installation complete. RUN_GAME.bat will prefer this isolated environment.
echo Run RUN_RUNTIME_PROBE.bat before gameplay if the previous build silently exited.
pause
exit /b 0

:FAIL
echo Dependency installation failed.
pause
exit /b 1
