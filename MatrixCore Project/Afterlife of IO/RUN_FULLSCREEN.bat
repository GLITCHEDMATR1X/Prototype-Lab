@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call RUN_GAME.bat --fullscreen %*
exit /b %ERRORLEVEL%
