@echo off
cd /d "%~dp0"
py main.py --legacy-renderer
if errorlevel 1 pause
