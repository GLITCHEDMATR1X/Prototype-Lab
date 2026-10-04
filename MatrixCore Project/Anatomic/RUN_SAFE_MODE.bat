@echo off
call "%~dp0RUN_ASCII_MATTER.bat" --safe-mode --windowed %*
exit /b %ERRORLEVEL%
