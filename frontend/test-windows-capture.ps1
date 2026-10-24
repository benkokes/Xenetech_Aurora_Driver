$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$frameworkPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$buildPath = Join-Path $projectRoot 'build\frontend'
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
$probePath = Join-Path $buildPath 'Aurora.PrintCaptureProbe.exe'
$references = @('WindowsBase', 'System.Printing') | ForEach-Object { '/reference:' + (Join-Path $frameworkPath ('WPF\' + $_ + '.dll')) }
$references += '/reference:' + (Join-Path $frameworkPath 'System.Drawing.dll')
& (Join-Path $frameworkPath 'csc.exe') /nologo /platform:x64 /warnaserror+ ('/out:' + $probePath) @references (Join-Path $PSScriptRoot 'PrintCaptureProbe.cs')
if ($LASTEXITCODE -ne 0) { throw 'Probe compilation failed.' }
& $probePath
if ($LASTEXITCODE -ne 0) { throw 'Local capture print failed.' }
