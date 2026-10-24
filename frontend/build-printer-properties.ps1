param([switch]$Test)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$output=Join-Path $projectRoot 'build\printer-ui'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$importer=Join-Path $output 'Aurora.BuildPrinterInterop.exe'
& $compiler /nologo /platform:x64 /warnaserror+ ('/out:'+$importer) (Join-Path $PSScriptRoot 'BuildPrinterInterop.cs')
if($LASTEXITCODE -ne 0) { throw 'COM importer compilation failed.' }
$typeLib=(Get-ItemProperty 'HKLM:\SOFTWARE\Classes\TypeLib\{91CE54EE-C67C-4B46-A4FF-99416F27A8BF}\1.0\0\win64').'(default)'
if(-not $typeLib) { throw 'Windows printer-extension COM type library is unavailable.' }
$interop=Join-Path $output 'Interop.PrinterExtensionLib.dll'
& $importer $typeLib $interop | Out-Null
if($LASTEXITCODE -ne 0) { throw 'Windows COM type-library import failed.' }
$sources=@((Join-Path $PSScriptRoot 'PrinterPreferences.cs'),(Join-Path $PSScriptRoot 'MaterialProfiles.cs'),(Join-Path $PSScriptRoot 'PrinterExtension.cs'),(Join-Path $PSScriptRoot 'ClassicSettings.cs'),(Join-Path $PSScriptRoot 'ClassicTicket.cs'),(Join-Path $PSScriptRoot 'ClassicPreferencesForm.cs'))
$references=@('/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:Microsoft.CSharp.dll',('/reference:'+$interop))
$executable=Join-Path $output 'Aurora.PrinterProperties.exe'
$target='/target:winexe'
$entry='/main:Aurora.Frontend.PrinterExtensionProgram'
if($Test) {
    $sources+=Join-Path $PSScriptRoot 'PrinterPreferencesTests.cs'
    foreach($assembly in @('System.Printing','WindowsBase','ReachFramework')) {
        $references+='/reference:'+(Join-Path $env:WINDIR ('Microsoft.NET\Framework64\v4.0.30319\WPF\'+$assembly+'.dll'))
    }
    $executable=Join-Path $output 'Aurora.PrinterProperties.Tests.exe'
    $target='/target:exe'
    $entry='/main:Aurora.Frontend.PrinterPreferencesTests'
}
& $compiler /nologo $target /platform:x64 /codepage:65001 /optimize+ /warnaserror+ $entry ('/out:'+$executable) @references @sources
if($LASTEXITCODE -ne 0) { throw 'Printer Properties compilation failed.' }
if($Test) {
    & $executable (Join-Path $projectRoot 'runtime\native-printer-inspection-r4')
    if($LASTEXITCODE -ne 0) { throw 'Printer Properties tests failed.' }
}
Write-Output $executable
