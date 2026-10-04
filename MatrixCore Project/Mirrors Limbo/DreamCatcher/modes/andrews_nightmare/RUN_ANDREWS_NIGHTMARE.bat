@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "GX_SEARCH=%~dp0"
:search_parent
for %%R in (runtime private_runtime) do call :try_runtime "%GX_SEARCH%\%%R\python.exe"
if defined GX_PY goto :private_found
for %%P in ("%GX_SEARCH%\..") do set "GX_PARENT=%%~fP"
if /i "%GX_PARENT%"=="%GX_SEARCH%" goto :system_python
set "GX_SEARCH=%GX_PARENT%"
goto :search_parent
:try_runtime
if defined GX_PY exit /b
if not exist "%~1" exit /b
"%~1" -c "from panda3d.core import PandaSystem; raise SystemExit(0 if PandaSystem.getVersionString()=='1.10.16' else 1)" >nul 2>nul
if not errorlevel 1 set "GX_PY=%~1"
exit /b
:private_found
"%GX_PY%" "%~dp0main.py" %*
goto :finished
:system_python
py -3.12 -c "from panda3d.core import PandaSystem; raise SystemExit(0 if PandaSystem.getVersionString()=='1.10.16' else 1)" >nul 2>nul
if not errorlevel 1 goto :py312
python -c "from panda3d.core import PandaSystem; raise SystemExit(0 if PandaSystem.getVersionString()=='1.10.16' else 1)" >nul 2>nul
if not errorlevel 1 goto :python
 echo Python with Panda3D 1.10.16 was not found. Use the Lab runtime installer.
pause
exit /b 3
:py312
py -3.12 "%~dp0main.py" %*
goto :finished
:python
python "%~dp0main.py" %*
:finished
set "GX_EXIT=%errorlevel%"
if "%GX_EXIT%"=="0" exit /b 0
echo Game exited with code %GX_EXIT%. Check its startup logs.
pause
exit /b %GX_EXIT%
