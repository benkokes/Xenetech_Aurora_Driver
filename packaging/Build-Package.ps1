[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Python,[string]$Name='AuroraJobServer-0.6.0-preview6-win-x64')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$output=Join-Path $root ('dist\'+$Name)
if(Test-Path -LiteralPath $output){throw 'Choose a new package name; previous artifacts are immutable.'}
$native=Join-Path $root 'build\frontend\Aurora.XpsIntake.exe'
$driver=Join-Path $root 'build\printer\AuroraV4-0.5.3-r11'
$priorPythonPath=$env:PYTHONPATH
try{
    $env:PYTHONPATH=Join-Path $root 'build\packaging-deps'
    & $Python -X utf8 -m PyInstaller --noconfirm --onedir --windowed --name AuroraJobServer --distpath (Join-Path $output 'app') --workpath (Join-Path $root ('build\packaging-work\'+$Name)) --specpath (Join-Path $root 'build\packaging-spec') --paths $root --add-data ($native+';native') --exclude-module tests (Join-Path $root 'run-desktop-jobserver.pyw')
    if($LASTEXITCODE -ne 0){throw 'Standalone application build failed.'}
}finally{$env:PYTHONPATH=$priorPythonPath}
foreach($required in @('_internal\_tkinter.pyd','_internal\_tcl_data\init.tcl','_internal\_tk_data\tk.tcl')){
    if(-not (Test-Path -LiteralPath (Join-Path (Join-Path $output 'app\AuroraJobServer') $required))){throw ('Missing bundled GUI dependency: '+$required)}
}
Copy-Item -LiteralPath $driver -Destination (Join-Path $output 'driver') -Recurse
$signatureMetadataPath=Join-Path $output 'driver\test-signing.json'
$signatureMetadata=Get-Content -LiteralPath $signatureMetadataPath -Raw | ConvertFrom-Json
$signatureMetadata.certificate_file='AuroraLocalTest.cer'
$signatureMetadata.trusted_in_windows=$null
$signatureMetadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $signatureMetadataPath -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $root 'runtime\printer-test-signing\AuroraLocalTest.cer') -Destination (Join-Path $output 'AuroraLocalTest.cer')
Copy-Item -LiteralPath (Join-Path $root 'build\frontend\Aurora.InstallPrinter.exe') -Destination (Join-Path $output 'Aurora.InstallPrinter.exe')
foreach($file in @('Setup.ps1','Uninstall.ps1','PACKAGE-README.txt')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $output $file)}
$notices=Join-Path $output 'third-party-notices'
New-Item -ItemType Directory -Path $notices | Out-Null
$deps=Join-Path $root 'build\packaging-deps'
Get-ChildItem -LiteralPath $deps -Directory -Filter '*.dist-info' | ForEach-Object {
    $record=$_;Get-ChildItem -LiteralPath $record.FullName -Recurse -File | Where-Object {$_.Name -match '^(LICENSE|COPYING|NOTICE)'} | ForEach-Object {
        $relative=$_.FullName.Substring($record.FullName.Length+1)
        $dest=Join-Path (Join-Path $notices $record.Name) $relative
        New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $dest
    }
}
$pythonLicense=Join-Path (Split-Path $Python -Parent) 'LICENSE.txt'
if(Test-Path -LiteralPath $pythonLicense){Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $notices 'Python-LICENSE.txt')}
foreach($library in @('tcl8.6','tk8.6')){
    $license=Join-Path (Split-Path $Python -Parent) ('tcl\'+$library+'\license.terms')
    if(Test-Path -LiteralPath $license){Copy-Item -LiteralPath $license -Destination (Join-Path $notices ($library+'-license.terms'))}
}
if(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'licenses\Tcl-8.6.12-license.terms')){Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'licenses\Tcl-8.6.12-license.terms') -Destination $notices}
$files=[ordered]@{}
Get-ChildItem -LiteralPath $output -Recurse -File | Sort-Object FullName | ForEach-Object {
    $relative=$_.FullName.Substring($output.Length+1).Replace('\','/')
    if($relative -match '(?i)\.(pfx|p12|key)$'){throw 'Private signing material must never enter a package.'}
    $files[$relative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$wheels=[ordered]@{}
Get-ChildItem -LiteralPath (Join-Path $root 'build\packaging-wheels') -File | Sort-Object Name | ForEach-Object {$wheels[$_.Name]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$acceptancePath=Join-Path $root 'runtime\color-raster-mixed-integration-20261022\staged-mixed-test-r1\physical-test-r2\physical-acceptance.json'
$accepted=$false
if(Test-Path -LiteralPath $acceptancePath){
    $acceptance=Get-Content -LiteralPath $acceptancePath -Raw | ConvertFrom-Json
    $accepted=$acceptance.state -eq 'physically_accepted_per_color_raster_and_mixed_167_dpi' -and $acceptance.cg_sha256 -eq 'fd0857825e3477d707a586af984edd8655abff73303a2465f5cd5de554010014' -and $acceptance.exact_full_wire_plan -eq $true
}
if(-not $accepted){throw 'Record the verified physical color acceptance before packaging the enabled pipeline.'}
$manifest=[ordered]@{schema_version=1;name=$Name;release_channel='development-preview';built_utc=[DateTime]::UtcNow.ToString('o');architecture='x64';bundled_python=$true;driver_version='0.5.3-r11';print_pipeline_version=4;startup_printing_enabled=$true;public_release_signature=$false;windows11_validated=$false;per_color_raster_hardware_accepted=$accepted;per_color_mixed_hardware_accepted=$accepted;files=$files;packaging_wheels=$wheels}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $output 'package-manifest.json') -Encoding UTF8
Compress-Archive -LiteralPath $output -DestinationPath ($output+'.zip')
Get-FileHash -LiteralPath ($output+'.zip') -Algorithm SHA256 | Format-List
Write-Output $output
