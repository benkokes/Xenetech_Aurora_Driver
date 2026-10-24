param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$frameworkPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$buildPath = Join-Path $projectRoot 'build\frontend'
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
$programPath = Join-Path $buildPath 'Aurora.ConfigureCapturePrinter.exe'
$references = @('WindowsBase', 'System.Printing', 'ReachFramework') | ForEach-Object { '/reference:' + (Join-Path $frameworkPath ('WPF\' + $_ + '.dll')) }
$references += '/reference:' + (Join-Path $frameworkPath 'System.Drawing.dll')
& (Join-Path $frameworkPath 'csc.exe') /nologo /platform:x64 /warnaserror+ ('/out:' + $programPath) @references (Join-Path $PSScriptRoot 'ConfigureCapturePrinter.cs') (Join-Path $PSScriptRoot 'CapturePaper.cs')
if ($LASTEXITCODE -ne 0) { throw 'Configuration tool compilation failed.' }
$recordPath = Join-Path $projectRoot ('runtime\capture-printer-settings\' + [Guid]::NewGuid().ToString('N'))
if ($Apply) { & $programPath $recordPath --apply } else { & $programPath $recordPath }
if ($LASTEXITCODE -ne 0) { throw ('Capture printer configuration failed. Evidence: ' + $recordPath) }
Write-Output ('Saved settings evidence: ' + $recordPath)
