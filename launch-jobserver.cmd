@echo off
setlocal
cd /d "%~dp0"
set "auroraPython=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if exist "%auroraPython%" goto launch
set "auroraPython=pythonw"
:launch
start "" "%auroraPython%" "%~dp0run-desktop-jobserver.pyw" --state "%~dp0runtime\desktop-jobserver" %*
if errorlevel 1 pause
