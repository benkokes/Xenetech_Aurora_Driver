[CmdletBinding(SupportsShouldProcess)]
param([switch]$RemovePrinter)
$ErrorActionPreference='Stop'
$target=[IO.Path]::GetFullPath((Join-Path $env:ProgramFiles 'AuroraJobServer'))
if((Split-Path $target -Leaf) -ne 'AuroraJobServer' -or (Split-Path $target -Parent) -ne [IO.Path]::GetFullPath($env:ProgramFiles)){throw 'Unexpected application directory.'}
if(Get-Process -Name AuroraJobServer -ErrorAction SilentlyContinue){throw 'Close Aurora JobServer before uninstalling.'}
if(Test-Path -LiteralPath $target){
    $receipt=Get-Content -LiteralPath (Join-Path $target 'install-receipt.json') -Raw | ConvertFrom-Json
    if($receipt.application -ne 'AuroraJobServer' -or $receipt.schema_version -ne 1){throw 'Application installation identity could not be verified.'}
    $known=@('install-receipt.json')
    foreach($file in $receipt.files.PSObject.Properties){
        $path=[IO.Path]::GetFullPath((Join-Path $target $file.Name))
        if(-not $path.StartsWith($target+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid installed path.'}
        if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.Value){throw 'Installed application changed; preserve it for reviewed removal.'}
        $known+=$file.Name.Replace('/','\')
    }
    foreach($file in Get-ChildItem -LiteralPath $target -Recurse -File){
        if($file.FullName.Substring($target.Length+1) -notin $known){throw 'Unexpected files in application folder; nothing removed.'}
    }
}
if($RemovePrinter){
    $printer=Get-Printer -Name 'Aurora JobServer (Test Capture)' -ErrorAction SilentlyContinue
    if($printer -and ($printer.DriverName -ne 'Aurora JobServer XPS Bridge' -or $printer.PortName -ne 'AuroraDirect_LPR_Loopback')){throw 'Conflicting printer; left unchanged.'}
    if($printer -and $PSCmdlet.ShouldProcess($printer.Name,'Remove Aurora printer queue')){Remove-Printer -Name $printer.Name}
}
if((Test-Path -LiteralPath $target) -and $PSCmdlet.ShouldProcess($target,'Remove installed application files')){Remove-Item -LiteralPath $target -Recurse}
$shortcut=Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Aurora JobServer.lnk'
if((Test-Path -LiteralPath $shortcut) -and $PSCmdlet.ShouldProcess($shortcut,'Remove Start shortcut')){Remove-Item -LiteralPath $shortcut}
Write-Output 'User records, startup registry entries, driver store, printer port and certificate trust are retained. Turn off Start with Windows in JobServer before uninstalling.'
