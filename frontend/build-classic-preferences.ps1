param([switch]$Test,[string]$ReviewDirectory)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$output=Join-Path $projectRoot 'build\classic-properties'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sources=@((Join-Path $PSScriptRoot 'ClassicSettings.cs'),(Join-Path $PSScriptRoot 'ClassicTicket.cs'),(Join-Path $PSScriptRoot 'ClassicPreferencesForm.cs'))
$target='/target:winexe';$entry='/main:Aurora.Frontend.ClassicPreferencesProgram';$executable=Join-Path $output 'Aurora.ClassicProperties.Preview.exe'
if($Test) {
    $target='/target:exe';$entry='/main:Aurora.Frontend.ClassicPreferencesTests';$sources+=Join-Path $PSScriptRoot 'ClassicPreferencesTests.cs'
    $executable=Join-Path $output 'Aurora.ClassicProperties.Tests.exe'
} else {$sources+=Join-Path $PSScriptRoot 'ClassicPreferencesProgram.cs'}
& $compiler /nologo /platform:x64 /codepage:65001 /warnaserror+ /optimize+ $target $entry ('/out:'+$executable) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:Microsoft.CSharp.dll @sources
if($LASTEXITCODE -ne 0) {throw 'Complete-controls build failed.'}
if($Test) {
    if(-not $ReviewDirectory) {$ReviewDirectory=Join-Path $projectRoot 'runtime\classic-properties-review'}
    & $executable $ReviewDirectory
    if($LASTEXITCODE -ne 0) {throw 'Complete-controls tests failed.'}
}
Write-Output $executable
