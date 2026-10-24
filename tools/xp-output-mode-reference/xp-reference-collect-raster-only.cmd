@echo off
setlocal
rem Read/copy only: leaves originals in the watched inbox.
set "AURORA_REFERENCE_DEST=%~dp0output-raster-only-%RANDOM%-%RANDOM%"
if exist "%AURORA_REFERENCE_DEST%" goto collision
mkdir "%AURORA_REFERENCE_DEST%"
if errorlevel 1 goto failed
echo requested_output_mode=raster-only > "%AURORA_REFERENCE_DEST%\comparison-label.txt"
echo collected_at=%DATE% %TIME% >> "%AURORA_REFERENCE_DEST%\comparison-label.txt"
dir /a /-c /t:w "C:\xfiles\etherin" > "%AURORA_REFERENCE_DEST%\inbox-list.txt" 2>&1
if not exist "C:\xfiles\etherin\*" goto missing
xcopy "C:\xfiles\etherin\*" "%AURORA_REFERENCE_DEST%\inbox\" /E /I /H /K
if errorlevel 2 goto failed
echo.
echo Captured files copied to:
echo %AURORA_REFERENCE_DEST%
echo IMPORTANT: originals remain in C:\xfiles\etherin.
echo Keep XP network disconnected and JobServer closed. Tell Codex the raster-only reference was collected.
pause
exit /b 0
:missing
echo No inbox files found. Keep XP offline and report what happened when printing.
pause
exit /b 1
:collision
echo Capture folder already exists. Run this script again.
pause
exit /b 1
:failed
echo Copy failed. Keep XP offline and JobServer closed; report the error.
pause
exit /b 1
