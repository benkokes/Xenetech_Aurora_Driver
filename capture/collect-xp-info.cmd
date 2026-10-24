@echo off
setlocal
rem Run on the working XP computer. Reads settings and copies two driver files.
rem Does not install software, change settings, or contact the engraver.
set "captureDir=%~dp0capture-%RANDOM%-%RANDOM%"
if exist "%captureDir%" goto collision
mkdir "%captureDir%"
if errorlevel 1 goto failed
ver > "%captureDir%\windows-version.txt"
reg query "HKCU\Software\ExtraTech\JOBSERVER\HotWatch" /s > "%captureDir%\jobserver-hotwatch.txt" 2>&1
reg query "HKCU\Software\ExtraTech\JOBSERVER\Settings" /s > "%captureDir%\jobserver-settings.txt" 2>&1
reg query "HKCU\Software\Extratech\ConnMgr" /s > "%captureDir%\connections-user.txt" 2>&1
reg query "HKLM\Software\Extratech\ConnMgr" /s > "%captureDir%\connections-machine.txt" 2>&1
reg query "HKCU\Software\Xenetech Global, Incorporated 32\Engraver Driver" /s > "%captureDir%\laser-driver-settings.txt" 2>&1
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Print\Printers" > "%captureDir%\printer-names.txt" 2>&1
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Print\Printers\Xenetech Laser Engraver" /s > "%captureDir%\printer-configuration.txt" 2>&1
dir /a "%SystemRoot%\system32\spool\drivers\w32x86\3\xtlaser*" > "%captureDir%\installed-driver-files.txt" 2>&1
copy /b "%SystemRoot%\system32\spool\drivers\w32x86\3\xtlasergr.dll" "%captureDir%\xtlasergr.dll" > "%captureDir%\copy-log.txt" 2>&1
copy /b "%SystemRoot%\system32\spool\drivers\w32x86\3\xtlaserui.dll" "%captureDir%\xtlaserui.dll" >> "%captureDir%\copy-log.txt" 2>&1
echo Diagnostics saved to:
echo %captureDir%
echo Missing registry keys or driver files will be recorded in the text files.
pause
exit /b 0
:collision
echo Output folder already exists. Run this script again to choose another name.
pause
exit /b 1
:failed
echo Could not create the diagnostics folder beside this script.
echo Copy this script to a writable folder and run it again.
pause
exit /b 1
