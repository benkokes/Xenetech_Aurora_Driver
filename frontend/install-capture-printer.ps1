[CmdletBinding(SupportsShouldProcess)]
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$printerName = 'Aurora Capture (Preview Only)'
$portName = 'AuroraCapture_LPR_Loopback'
$driverName = 'Microsoft XPS Document Writer v4'
$printer = Get-Printer -Name $printerName -ErrorAction SilentlyContinue
$port = Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue
if ($printer -and ($printer.DriverName -ne $driverName -or $printer.PortName -ne $portName)) {
    throw 'The capture printer name is already used with different settings. No changes made.'
}
if ($port -and ($port.PrinterHostAddress -ne '127.0.0.1' -or [string]$port.Protocol -notin @('2', 'LPR') -or $port.LprQueueName -ne 'aurora-capture' -or -not $port.LprByteCounting)) {
    throw 'The capture port name is already used with different settings. No changes made.'
}
if ($Remove) {
    if ($printer) {
        if (Get-PrintJob -PrinterName $printerName) { throw 'The capture queue still has print jobs. Resolve those before removing it.' }
        if ($PSCmdlet.ShouldProcess($printerName, 'Remove local preview-only capture printer')) { Remove-Printer -Name $printerName }
    }
    if ($port) {
        $otherPrinters = @(Get-Printer | Where-Object PortName -eq $portName)
        if ($otherPrinters.Count -ne 0) { throw 'The capture port is still in use; it was retained.' }
        if ($PSCmdlet.ShouldProcess($portName, 'Remove local preview-only capture port')) { Remove-PrinterPort -Name $portName }
    }
    return
}
if (-not (Get-PrinterDriver -Name $driverName -ErrorAction SilentlyContinue)) {
    throw 'Enable Microsoft XPS Document Writer in Windows Features first. This script does not install another driver.'
}
if (-not $port -and $PSCmdlet.ShouldProcess($portName, 'Create byte-counted LPR port to 127.0.0.1 only')) {
    Add-PrinterPort -Name $portName -LprHostAddress '127.0.0.1' -LprQueueName 'aurora-capture' -LprByteCounting
}
if (-not $printer -and $PSCmdlet.ShouldProcess($printerName, 'Create local preview-only printer using the installed Microsoft XPS driver')) {
    Add-Printer -Name $printerName -DriverName $driverName -PortName $portName -Comment 'Local document capture only. Does not send to the laser.'
}
if (-not $WhatIfPreference) {
    if ($PSCmdlet.ShouldProcess($printerName, 'Set 30 by 18 inch capture media with prior-settings backup')) {
        & (Join-Path $PSScriptRoot 'configure-capture-printer.ps1') -Apply
    }
    Get-Printer -Name $printerName | Select-Object Name, DriverName, PortName
    Write-Output 'Start launch-print-capture.cmd before printing. Output is captured locally for analysis; no engraving occurs.'
}
