param(
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$StopFile,
    [int]$DurationSeconds = 600,
    [string]$VmId = '86b4c234-1ba8-4bf6-b47b-49f93e525f24'
)
$ErrorActionPreference = 'Stop'
$vboxPath = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
function Invoke-VBox([string[]]$Arguments) {
    $result = & $vboxPath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($result -join "`n") }
    return $result
}
if ($DurationSeconds -lt 1 -or $DurationSeconds -gt 1800) {
    throw 'Capture duration must be between 1 and 1800 seconds.'
}
if ((Test-Path -LiteralPath $OutputPath) -or (Test-Path -LiteralPath $StopFile)) {
    throw 'Output and stop paths must be new.'
}
$nicLine = Invoke-VBox -Arguments @('showvminfo', $VmId) | Where-Object { $_ -match '^NIC 1:' }
if ($nicLine -notmatch 'Trace: off \(file: none\)') {
    throw "Refusing to replace an existing trace configuration: $nicLine"
}
$traceConfigured = $false
try {
    $null = Invoke-VBox -Arguments @('controlvm', $VmId, 'nictracefile1', $OutputPath)
    $traceConfigured = $true
    $null = Invoke-VBox -Arguments @('controlvm', $VmId, 'nictrace1', 'on')
    $current = Invoke-VBox -Arguments @('showvminfo', $VmId) | Where-Object { $_ -match '^NIC 1:' }
    if ($current -notmatch 'Trace: on') { throw "Trace did not start: $current" }
    Write-Output "CAPTURE READY: $OutputPath"
    Write-Output "Stop file: $StopFile"
    $captureTimer = [Diagnostics.Stopwatch]::StartNew()
    while ($captureTimer.Elapsed.TotalSeconds -lt $DurationSeconds) {
        if (Test-Path -LiteralPath $StopFile) { break }
        Start-Sleep -Milliseconds 500
    }
}
finally {
    if ($traceConfigured) {
        try { $null = Invoke-VBox -Arguments @('controlvm', $VmId, 'nictrace1', 'off') }
        finally { $null = Invoke-VBox -Arguments @('controlvm', $VmId, 'nictracefile1', '') }
        Invoke-VBox -Arguments @('showvminfo', $VmId) | Where-Object { $_ -match '^NIC 1:' }
    }
}
Write-Output 'CAPTURE STOPPED'
Get-Item -LiteralPath $OutputPath | Select-Object FullName, Length

