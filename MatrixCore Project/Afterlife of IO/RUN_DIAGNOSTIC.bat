@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call RUN_GAME.bat --windowed --safe-mode %*
exit /b %ERRORLEVEL%
