@echo off
setlocal
cd /d "%~dp0"
set "EXITCODE=0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -c "import panda3d" >nul 2>nul
    if errorlevel 1 goto :missing_panda
    py main.py %*
    set "EXITCODE=%ERRORLEVEL%"
    goto :after_run
)

where python >nul 2>nul
if errorlevel 1 goto :missing_python
python -c "import panda3d" >nul 2>nul
if errorlevel 1 goto :missing_panda
python main.py %*
set "EXITCODE=%ERRORLEVEL%"

:after_run
if not "%EXITCODE%"=="0" (
    echo.
    echo Glyphbound encountered a runtime error. The traceback above is the useful part.
    echo Panda3D was found successfully, so reinstalling it is probably not necessary.
    echo.
    pause
)
goto :eof

:missing_python
echo.
echo Python was not found.
echo Install Python 3.12+ and try again.
echo.
pause
goto :eof

:missing_panda
echo.
echo Panda3D is not installed for the Python interpreter used by this launcher.
echo Install it with: py -m pip install panda3d
echo.
pause
