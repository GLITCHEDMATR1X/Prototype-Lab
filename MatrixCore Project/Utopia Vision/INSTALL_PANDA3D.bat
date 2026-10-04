@echo off
cd /d "%~dp0"
py -3.13 -m pip install panda3d==1.10.16
if errorlevel 1 (
  echo.
  echo Panda3D installation failed.
  pause
  exit /b 1
)
echo Panda3D 1.10.16 installed.
pause
