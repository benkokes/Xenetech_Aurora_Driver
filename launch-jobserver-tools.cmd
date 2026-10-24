@echo off
setlocal
cd /d "%~dp0"
set "auroraPython=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%auroraPython%" goto launch
set "auroraPython=python"
:launch
"%auroraPython%" -m aurora_jobserver gui
if errorlevel 1 pause
