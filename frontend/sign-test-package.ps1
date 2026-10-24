param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [Parameter(Mandatory=$true)][string]$SignToolPath,
    [switch]$ReuseIdentity,
    [string]$ExpectedThumbprint
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$signTool = (Resolve-Path -LiteralPath $SignToolPath).Path
if ((Get-AuthenticodeSignature -LiteralPath $signTool).Status -ne 'Valid') { throw 'SignTool must have a valid Microsoft signature.' }
$catalog = Join-Path $package 'Aurora.cat'
if (-not (Test-Path -LiteralPath $catalog)) { throw 'Generate the driver catalog before signing.' }
$keyDirectory = Join-Path $projectRoot 'runtime\printer-test-signing'
New-Item -ItemType Directory -Force -Path $keyDirectory | Out-Null
$pfxPath = Join-Path $keyDirectory 'AuroraLocalTest.pfx'
$cerPath = Join-Path $keyDirectory 'AuroraLocalTest.cer'
$secretPath = Join-Path $keyDirectory 'password.dpapi'
$rsa = $null
try {
    if ($ReuseIdentity) {
        if (-not $ExpectedThumbprint) { throw 'Pin the approved certificate thumbprint when reusing its signing identity.' }
        $certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new([IO.File]::ReadAllBytes($cerPath))
        if ($certificate.Thumbprint -ne $ExpectedThumbprint -or $certificate.Subject -ne 'CN=Aurora JobServer Local Development') { throw 'Unexpected development signing certificate.' }
        $securePassword = (Get-Content -LiteralPath $secretPath -Raw).Trim() | ConvertTo-SecureString
        $password = [System.Net.NetworkCredential]::new('AuroraLocalTest',$securePassword).Password
    } else {
    if (Test-Path -LiteralPath $pfxPath) { throw 'Signing identity already exists; do not replace it implicitly.' }
    $rsa = [System.Security.Cryptography.RSA]::Create(3072)
    $request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=Aurora JobServer Local Development', $rsa,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false,$false,0,$true))
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
        [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature,$true))
    $eku = [System.Security.Cryptography.OidCollection]::new()
    [void]$eku.Add([System.Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.3'))
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($eku,$true))
    $certificate = $request.CreateSelfSigned([DateTimeOffset]::UtcNow.AddMinutes(-5),[DateTimeOffset]::UtcNow.AddDays(90))
    $password = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    [IO.File]::WriteAllBytes($pfxPath,$certificate.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Pfx,$password))
    [IO.File]::WriteAllBytes($cerPath,$certificate.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
    $password | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath $secretPath
    }
    & $signTool sign /fd SHA256 /f $pfxPath /p $password $catalog
    if ($LASTEXITCODE -ne 0) { throw 'Test catalog signing failed.' }
    $record = [ordered]@{
        subject=$certificate.Subject; thumbprint=$certificate.Thumbprint
        not_after_utc=$certificate.NotAfter.ToUniversalTime().ToString('o')
        certificate_file=$cerPath; catalog_sha256=(Get-FileHash -LiteralPath $catalog -Algorithm SHA256).Hash.ToLowerInvariant()
        trusted_in_windows=(Test-Path ('Cert:\LocalMachine\Root\'+$certificate.Thumbprint)); certificate_stores_modified=$false
        purpose='Local development printer package; not a public release signature'
    }
    $record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $package 'test-signing.json') -Encoding utf8
    $record | ConvertTo-Json
    $certificate.Dispose()
} finally { if ($rsa) { $rsa.Dispose() }; $password = $null }
