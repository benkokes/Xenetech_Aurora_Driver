@echo off
setlocal
rem Read/copy only: does not print, connect, stop services, move or delete jobs.
set "AURORA_REFERENCE_DEST=%~dp0before-closing-%RANDOM%-%RANDOM%"
if exist "%AURORA_REFERENCE_DEST%" goto collision
mkdir "%AURORA_REFERENCE_DEST%"
if errorlevel 1 goto failed
dir /a /-c /t:w "C:\xfiles\etherin" > "%AURORA_REFERENCE_DEST%\inbox-list.txt" 2>&1
if not exist "C:\xfiles\etherin\*" goto empty
xcopy "C:\xfiles\etherin\*" "%AURORA_REFERENCE_DEST%\inbox\" /E /I /H /K
if errorlevel 2 goto failed
:empty
echo.
echo Backup saved to:
echo %AURORA_REFERENCE_DEST%
echo Now disconnect the XP VM network and close JobServer before printing.
echo JobServer may clear its inbox on exit. This backup script changes no jobs.
pause
exit /b 0
:collision
echo Backup folder already exists. Run this script again.
pause
exit /b 1
:failed
echo Backup failed. Keep JobServer and its inbox as they are; report the error.
pause
exit /b 1
