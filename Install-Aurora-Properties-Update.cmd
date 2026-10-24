@echo off
setlocal
cd /d "%~dp0"
echo Aurora Printer Properties update: travel-speed units, version 0.5.3.
echo Run as administrator. Laser resolution remains 167 DPI.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0frontend\install-properties-update.ps1"
if errorlevel 1 (
    echo Update did not complete. The saved result can be checked in the chat.
) else (
    echo Update finished. Close and reopen the CorelDRAW Print and Properties dialogs.
)
pause
