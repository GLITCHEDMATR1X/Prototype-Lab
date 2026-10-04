@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found.
  echo Install Python 3.13 and Panda3D 1.10.16 first.
  pause
  exit /b 1
)
py -3.13 main.py
if errorlevel 1 pause
