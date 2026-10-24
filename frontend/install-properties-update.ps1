[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$package=Join-Path $projectRoot 'build\printer\AuroraV4-0.5.3-r11'
$expectedThumbprint='2A5AC9C0A94B0B3AD79BD7C30EF897ADFD06F75F'
$signing=Get-Content -LiteralPath (Join-Path $package 'test-signing.json') -Raw | ConvertFrom-Json
if($signing.thumbprint -ne $expectedThumbprint) {throw 'Unexpected development signing identity.'}
$signature=Get-AuthenticodeSignature -LiteralPath (Join-Path $package 'Aurora.cat')
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $expectedThumbprint) {
    throw 'The update must have the already trusted development signature.'
}
if($WhatIfPreference) {
    & (Join-Path $PSScriptRoot 'install-direct-printer.ps1') -PackagePath $package -WhatIf
    return
}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run Install-Aurora-Properties-Update.cmd as administrator.'
}
$mutex=[Threading.Mutex]::new($false,'Local\AuroraJobServerCapturePrinterInstall')
try {$owned=$mutex.WaitOne(0)} catch [Threading.AbandonedMutexException] {$owned=$true}
if(-not $owned) {$mutex.Dispose();throw 'Another Aurora printer installation is already running.'}
$result=Join-Path $projectRoot 'runtime\printer-properties-r11-install.json'
Start-Transcript -LiteralPath (Join-Path $projectRoot 'runtime\printer-properties-r11-install.log') -Append | Out-Null
$exitCode=0
try {
    $desktop=Get-Content -LiteralPath (Join-Path $projectRoot 'runtime\desktop-jobserver\desktop-status.json') -Raw | ConvertFrom-Json
    if($desktop.mode -ne 'capture_only' -or $desktop.current_print) {throw 'Select Capture only and finish the current print before updating.'}
    if($desktop.preferences_schema_version -ne 2) {throw 'Reload the updated JobServer settings reader before installing these controls.'}
    if(2 -notin @($desktop.classic_preferences_versions)) {throw 'Restart JobServer in Capture only before installing the travel-speed units update.'}
    if(@(Get-PrintJob -PrinterName 'Aurora JobServer (Test Capture)' -ErrorAction Stop).Count) {throw 'The printer queue must be empty before updating.'}
    @{state='installing';package=$package;started_utc=[DateTime]::UtcNow.ToString('o');laser_dpi=167;certificate_trust_changed=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $result -Encoding utf8
    & (Join-Path $PSScriptRoot 'install-direct-printer.ps1') -PackagePath $package
    $driver=Get-PrinterDriver -Name 'Aurora JobServer XPS Bridge' -ErrorAction Stop
    $printer=Get-Printer -Name 'Aurora JobServer (Test Capture)' -ErrorAction Stop
    $nativeReport=Join-Path $projectRoot ('runtime\classic-native-roundtrip-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
    & (Join-Path $projectRoot 'build\classic-properties\Aurora.ClassicNativeRoundtrip.exe') $nativeReport
    if($LASTEXITCODE -ne 0) {throw ('Driver installed, but native complete-settings verification failed. Report: '+$nativeReport)}
    $qualityReport=Join-Path $projectRoot ('runtime\bitmap-quality-fix-20261020\installed-quality-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
    & (Join-Path $projectRoot 'build\printer-ui\BitmapQualityAudit.exe') $qualityReport verify
    if($LASTEXITCODE -ne 0) {throw ('Driver installed, but lossless-quality verification failed. Report: '+$qualityReport)}
    @{state='installed';package=$package;name=$printer.Name;port=$printer.PortName;inf_path=$driver.InfPath;
      finished_utc=[DateTime]::UtcNow.ToString('o');laser_dpi=167;native_roundtrip_report=$nativeReport;quality_report=$qualityReport;certificate_trust_changed=$false;laser_sender_started=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $result -Encoding utf8
} catch {
    $exitCode=1
    @{state='failed';error=$_.Exception.Message;finished_utc=[DateTime]::UtcNow.ToString('o');laser_sender_started=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $result -Encoding utf8
} finally {
    Stop-Transcript | Out-Null
    $mutex.ReleaseMutex();$mutex.Dispose()
}
exit $exitCode
