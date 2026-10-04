@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0..\..\INSTALL_PORTABLE_RUNTIME.bat" (
  call "%~dp0..\..\INSTALL_PORTABLE_RUNTIME.bat"
  exit /b %ERRORLEVEL%
)
echo This standalone source folder expects Panda3D 1.10.16.
echo Recommended public distribution: use the Pass 96 launcher package so Python and Panda3D are private and automatic.
pause
exit /b 2
