$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$output=Join-Path $projectRoot 'build\printer-ui\Aurora.NativePreferencesSession.Tests.exe'
$interop=Join-Path $projectRoot 'build\printer-ui\Interop.PrinterExtensionLib.dll'
$sources=@('ClassicSettings.cs','ClassicTicket.cs','ClassicPreferencesForm.cs','PrinterPreferences.cs','MaterialProfiles.cs','PrinterExtension.cs','NativePreferencesSessionTests.cs') | ForEach-Object {Join-Path $PSScriptRoot $_}
& $compiler /nologo /codepage:65001 /platform:x64 /warnaserror+ /main:Aurora.Frontend.NativePreferencesSessionTests ('/out:'+$output) /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:Microsoft.CSharp.dll ('/reference:'+$interop) @sources
if($LASTEXITCODE -ne 0) {throw 'Native session test compilation failed.'}
& $output (Join-Path $projectRoot 'runtime\native-printer-inspection-r8')
if($LASTEXITCODE -ne 0) {throw 'Native preference session checks failed.'}
