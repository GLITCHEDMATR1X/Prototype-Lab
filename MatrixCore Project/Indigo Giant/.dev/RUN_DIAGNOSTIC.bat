@echo off
setlocal
cd /d "%~dp0.."
title The Indigo Giant - diagnostic

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

echo Using: %PYEXE%
echo.
%PYEXE% "%~dp0diagnostic.py"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Diagnostic exit code: %EXITCODE%
echo Log: "%~dp0diagnostic.log"
if not "%EXITCODE%"=="0" echo Send .dev\diagnostic.log back for repair.
pause
exit /b %EXITCODE%
