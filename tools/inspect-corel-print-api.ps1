$ErrorActionPreference='Stop'
$taskApp=New-Object -ComObject CorelDRAW.Application.17
$taskDocument=$taskApp.ActiveDocument
if($null -eq $taskDocument){throw 'No active document; no print performed.'}
Write-Output 'PRINT SETTINGS'
$taskDocument.PrintSettings | Get-Member | Format-List Name,MemberType,Definition
Write-Output 'PRINTER COLLECTION'
$taskApp.Printers | Get-Member | Format-List Name,MemberType,Definition
Write-Output 'PRINTER COUNT'
$taskApp.Printers.Count
