@echo off
call "%~dp0RUN_ASCII_MATTER.bat" --fullscreen --width 1920 --height 1080 %*
exit /b %ERRORLEVEL%
