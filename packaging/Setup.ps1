[CmdletBinding(SupportsShouldProcess)]
param([switch]$ValidateOnly,[switch]$TrustDevelopmentCertificate)
$ErrorActionPreference='Stop'
$package=$PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $package 'package-manifest.json') -Raw | ConvertFrom-Json
foreach($file in $manifest.files.PSObject.Properties){
    $path=[IO.Path]::GetFullPath((Join-Path $package $file.Name))
    if(-not $path.StartsWith($package+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid manifest path.'}
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value){throw ('Package integrity failed: '+$file.Name)}
}
if(-not [Environment]::Is64BitProcess){throw 'Run the 64-bit Windows PowerShell.'}
$driverName='Aurora JobServer XPS Bridge';$printerName='Aurora JobServer (Test Capture)';$portName='AuroraDirect_LPR_Loopback'
$printer=Get-Printer -Name $printerName -ErrorAction SilentlyContinue
$port=Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue
if($printer -and ($printer.DriverName -ne $driverName -or $printer.PortName -ne $portName)){throw 'Conflicting existing printer; left unchanged.'}
if($port -and ($port.PrinterHostAddress -ne '127.0.0.1' -or [string]$port.Protocol -notin @('2','LPR') -or $port.LprQueueName -ne 'aurora-direct' -or -not $port.LprByteCounting)){throw 'Conflicting existing printer port; left unchanged.'}
$thumb='2A5AC9C0A94B0B3AD79BD7C30EF897ADFD06F75F'
$certificate=New-Object Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $package 'AuroraLocalTest.cer')
if($certificate.Thumbprint -ne $thumb -or $certificate.NotAfter -lt (Get-Date)){throw 'Unexpected or expired development certificate.'}
if($ValidateOnly){Write-Output 'Package hashes, certificate identity and local printer configuration validated. No changes made.';return}
if($WhatIfPreference){[void]$PSCmdlet.ShouldProcess('Aurora JobServer','Install application, verified printer driver and local printer');return}
$admin=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run Setup in an administrator PowerShell.'}
$destination=Join-Path $env:ProgramFiles 'AuroraJobServer'
if(Test-Path -LiteralPath $destination){throw 'An application installation already exists. Preview upgrades require a reviewed migration.'}
$programs=[Environment]::GetFolderPath('CommonPrograms')
$shortcutPath=Join-Path $programs 'Aurora JobServer.lnk'
if(Test-Path -LiteralPath $shortcutPath){throw 'An existing Start shortcut was left unchanged.'}
$rootTrusted=Test-Path -LiteralPath ('Cert:\LocalMachine\Root\'+$thumb)
$publisherTrusted=Test-Path -LiteralPath ('Cert:\LocalMachine\TrustedPublisher\'+$thumb)
if(-not ($rootTrusted -and $publisherTrusted)){
    if(-not $TrustDevelopmentCertificate){throw 'This preview uses a local development certificate. Review PACKAGE-README.txt; explicit -TrustDevelopmentCertificate is required to add machine trust.'}
    if(-not $rootTrusted){Import-Certificate -FilePath (Join-Path $package 'AuroraLocalTest.cer') -CertStoreLocation Cert:\LocalMachine\Root | Out-Null}
    if(-not $publisherTrusted){Import-Certificate -FilePath (Join-Path $package 'AuroraLocalTest.cer') -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null}
}
$catalog=Join-Path $package 'driver\aurora.cat'
$signature=Get-AuthenticodeSignature -LiteralPath $catalog
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $thumb){throw 'Printer catalog signature is not trusted and valid.'}
& (Join-Path $package 'Aurora.InstallPrinter.exe') (Join-Path $package 'driver\Aurora.inf') $driverName
if($LASTEXITCODE -ne 0){throw 'Windows rejected the printer package.'}
if(-not $port){Add-PrinterPort -Name $portName -LprHostAddress '127.0.0.1' -LprQueueName 'aurora-direct' -LprByteCounting}
if(-not $printer){Add-Printer -Name $printerName -DriverName $driverName -PortName $portName -Comment 'Aurora JobServer local capture bridge. Laser delivery requires Enable laser printing.'}
Copy-Item -LiteralPath (Join-Path $package 'app\AuroraJobServer') -Destination $destination -Recurse
$ownedFiles=[ordered]@{}
foreach($file in $manifest.files.PSObject.Properties){
    if($file.Name.StartsWith('app/AuroraJobServer/')){$ownedFiles[$file.Name.Substring('app/AuroraJobServer/'.Length)]=$file.Value}
}
@{schema_version=1;application='AuroraJobServer';package=$manifest.name;files=$ownedFiles} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destination 'install-receipt.json') -Encoding UTF8
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=Join-Path $destination 'AuroraJobServer.exe';$shortcut.WorkingDirectory=$destination;$shortcut.Save()
Write-Output 'Installed. Open Aurora JobServer from Start. New print delivery is enabled on normal launch; old captures stay held. Setup has not started JobServer or sent a job.'
