$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$output=Join-Path $projectRoot 'build\classic-properties\Aurora.ClassicNativeRoundtrip.exe'
$references=@('/reference:System.Printing.dll','/reference:ReachFramework.dll','/reference:WindowsBase.dll') | ForEach-Object {
    '/reference:'+(Join-Path $env:WINDIR ('Microsoft.NET\Framework64\v4.0.30319\WPF\'+($_ -replace '^/reference:','')))
}
$references+='/reference:Microsoft.CSharp.dll'
& $compiler /nologo /codepage:65001 /platform:x64 /warnaserror+ ('/out:'+$output) @references (Join-Path $PSScriptRoot 'ClassicSettings.cs') (Join-Path $PSScriptRoot 'ClassicTicket.cs') (Join-Path $PSScriptRoot 'ClassicNativeRoundtrip.cs')
if($LASTEXITCODE -ne 0) {throw 'Native settings roundtrip test build failed.'}
Write-Output $output
