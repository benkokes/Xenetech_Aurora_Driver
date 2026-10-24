[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory=$true)][string]$PackagePath)
$ErrorActionPreference = 'Stop'
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$driverName = 'Aurora JobServer XPS Bridge'
$printerName = 'Aurora JobServer (Test Capture)'
$portName = 'AuroraDirect_LPR_Loopback'
$build = Get-Content -LiteralPath (Join-Path $package 'package-build.json') -Raw | ConvertFrom-Json
if ($build.driver_name -ne $driverName) { throw 'Unexpected driver identity.' }
foreach ($file in $build.files.PSObject.Properties) {
    if ($file.Name -notin @('Aurora.inf','Aurora.gpd','Aurora-manifest.ini','Aurora-pipelineconfig.xml','Aurora.PrinterProperties.exe','Interop.PrinterExtensionLib.dll','AuroraSettings.js','Aurora-devmode.xml')) { throw 'Unexpected package filename.' }
    if ((Get-FileHash -LiteralPath (Join-Path $package $file.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value) { throw "Package integrity failed: $($file.Name)" }
}
$native = Get-Content -LiteralPath (Join-Path $package 'native-validation.json') -Raw | ConvertFrom-Json
if ($native.state -ne 'native_feature_expansion_passed' -or $native.gpd_sha256 -ne $build.files.'Aurora.gpd') {
    throw 'Validate native GPD feature expansion for this exact package before installing.'
}
$signed = Get-Content -LiteralPath (Join-Path $package 'test-signing.json') -Raw | ConvertFrom-Json
$catalog = Join-Path $package 'Aurora.cat'
if ((Get-FileHash -LiteralPath $catalog -Algorithm SHA256).Hash.ToLowerInvariant() -ne $signed.catalog_sha256) { throw 'Catalog changed after signing.' }
if ($WhatIfPreference) {
    [void]$PSCmdlet.ShouldProcess($driverName,'Install verified signed v4 package')
    [void]$PSCmdlet.ShouldProcess($portName,'Create LPR port 127.0.0.1:515, queue aurora-direct')
    [void]$PSCmdlet.ShouldProcess($printerName,'Create separate test-capture printer; no receiver or laser sender started')
    return
}
$signature = Get-AuthenticodeSignature -LiteralPath $catalog
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $signed.thumbprint) {
    throw 'Catalog signer must first be explicitly trusted for this development test.'
}
$printer = Get-Printer -Name $printerName -ErrorAction SilentlyContinue
$port = Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue
if ($printer -and ($printer.DriverName -ne $driverName -or $printer.PortName -ne $portName)) { throw 'Conflicting printer name.' }
if ($port -and ($port.PrinterHostAddress -ne '127.0.0.1' -or [string]$port.Protocol -notin @('2','LPR') -or $port.LprQueueName -ne 'aurora-direct' -or -not $port.LprByteCounting)) { throw 'Conflicting local port.' }
$projectRoot = Split-Path $PSScriptRoot -Parent
$helper = Join-Path $projectRoot 'build\frontend\Aurora.InstallPrinter.exe'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if ($PSCmdlet.ShouldProcess($driverName,'Stage and install the signed printer package')) {
    & $compiler /nologo /platform:x64 /warnaserror+ ('/out:'+$helper) (Join-Path $PSScriptRoot 'PrinterPackageInstall.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Installer helper compilation failed.' }
    & $helper --check-api
    if ($LASTEXITCODE -ne 0) { throw 'Windows printer API preflight failed.' }
    & $helper (Join-Path $package 'Aurora.inf') $driverName
    if ($LASTEXITCODE -ne 0) { throw 'Windows rejected the printer package.' }
}
if (-not $port -and $PSCmdlet.ShouldProcess($portName,'Create local LPR test port')) {
    Add-PrinterPort -Name $portName -LprHostAddress '127.0.0.1' -LprQueueName 'aurora-direct' -LprByteCounting
}
if (-not $printer -and $PSCmdlet.ShouldProcess($printerName,'Create isolated capture-only test printer')) {
    Add-Printer -Name $printerName -DriverName $driverName -PortName $portName -Comment 'Local validation of laser Properties; no automatic laser sender is running.'
}
