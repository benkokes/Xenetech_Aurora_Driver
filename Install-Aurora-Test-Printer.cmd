@echo off
setlocal
cd /d "%~dp0"
echo Aurora capture-only test printer setup
echo Run this file as administrator. No laser sender will be started.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\install-native-printer-20261018.ps1"
if errorlevel 1 (
    echo Setup did not complete. Return to the chat for the saved error details.
) else (
    echo Setup finished. Return to the chat so the printer can be checked.
)
pause
