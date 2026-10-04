@echo off
setlocal
cd /d "%~dp0"
title Indigo Giant Pass 43 Diagnostic

echo ============================================================
echo   INDIGO GIANT PASS 37 - STARTUP DIAGNOSTIC
echo ============================================================
echo.

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
    echo Install/use the Python environment that previously ran Indigo Giant.
    echo.
    pause
    exit /b 9009
)

echo Using: %PYEXE%
echo.
%PYEXE% "%~dp0INDIGO_DIAGNOSTIC.py"
set "EXITCODE=%ERRORLEVEL%"

echo.
echo Diagnostic exit code: %EXITCODE%
echo Log: "%~dp0indigo_diagnostic.log"
echo.
if not "%EXITCODE%"=="0" echo Send indigo_diagnostic.log back for repair.
pause
exit /b %EXITCODE%
