[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory=$true)][string]$PackagePath,
      [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$ExpectedThumbprint,
      [switch]$Apply,[switch]$Remove)
$ErrorActionPreference = 'Stop'
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$record = Get-Content -LiteralPath (Join-Path $package 'test-signing.json') -Raw | ConvertFrom-Json
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new([IO.File]::ReadAllBytes($record.certificate_file))
if ($certificate.Subject -ne 'CN=Aurora JobServer Local Development' -or $certificate.Thumbprint -ne $record.thumbprint -or $certificate.Thumbprint -ne $ExpectedThumbprint.ToUpperInvariant()) { throw 'Unexpected test certificate.' }
if ($certificate.HasPrivateKey) { throw 'Only the public development certificate may be trusted.' }
foreach ($store in @('Root','TrustedPublisher')) {
    $destination = 'Cert:\LocalMachine\'+$store
    $entry = $destination+'\'+$certificate.Thumbprint
    if (-not $Apply) {
        $verb = if ($Remove) { 'Would remove ' } else { 'Would trust ' }
        Write-Output ($verb+$certificate.Thumbprint+' in '+$destination)
        continue
    }
    if ($Remove) {
        if ((Test-Path -LiteralPath $entry) -and $PSCmdlet.ShouldProcess($entry,'Remove only this project test certificate')) { Remove-Item -LiteralPath $entry }
    } elseif (-not (Test-Path -LiteralPath $entry) -and $PSCmdlet.ShouldProcess($entry,'Trust project development signer for local printer testing')) {
        Import-Certificate -FilePath $record.certificate_file -CertStoreLocation $destination | Out-Null
    }
}
$certificate.Dispose()
