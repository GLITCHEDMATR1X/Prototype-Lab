@echo off
setlocal
cd /d "%~dp0.."
title The Indigo Giant - checks

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

echo Running every check (a few minutes). Each one starts the game without a window.
echo.
%PYEXE% "%~dp0run_checks.py" %*
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Summary: "%~dp0check_results.txt"   Full logs: "%~dp0check_logs\"
pause
exit /b %EXITCODE%
