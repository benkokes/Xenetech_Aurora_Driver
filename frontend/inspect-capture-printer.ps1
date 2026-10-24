param([switch]$Forms)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$frameworkPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$buildPath = Join-Path $projectRoot 'build\frontend'
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
$programPath = Join-Path $buildPath 'Aurora.InspectCapturePrinter.exe'
$references = @('WindowsBase', 'System.Printing') | ForEach-Object { '/reference:' + (Join-Path $frameworkPath ('WPF\' + $_ + '.dll')) }
$references += '/reference:' + (Join-Path $frameworkPath 'System.Drawing.dll')
& (Join-Path $frameworkPath 'csc.exe') /nologo /platform:x64 /warnaserror+ ('/out:' + $programPath) @references (Join-Path $PSScriptRoot 'InspectCapturePrinter.cs') (Join-Path $PSScriptRoot 'CapturePaper.cs')
if ($LASTEXITCODE -ne 0) { throw 'Inspection tool compilation failed.' }
if ($Forms) { & $programPath --forms } else { & $programPath }
if ($LASTEXITCODE -ne 0) { throw 'Capture printer inspection failed.' }
