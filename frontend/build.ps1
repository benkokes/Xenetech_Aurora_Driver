param([switch]$Test, [string]$Destination, [string]$TestArtifacts, [switch]$SemanticCampaign)
$ErrorActionPreference = 'Stop'
if($Test -and $SemanticCampaign){throw 'Choose ordinary tests or the semantic campaign.'}
$projectRoot = Split-Path $PSScriptRoot -Parent
$frameworkPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$compilerPath = Join-Path $frameworkPath 'csc.exe'
if (-not (Test-Path -LiteralPath $compilerPath)) { throw 'The 64-bit .NET Framework C# compiler is required.' }
$buildPath = if ($Destination) { [IO.Path]::GetFullPath($Destination) } else { Join-Path $projectRoot 'build\frontend' }
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
$references = @('WindowsBase', 'PresentationCore', 'PresentationFramework', 'ReachFramework', 'System.Printing') | ForEach-Object {
    '/reference:' + (Join-Path $frameworkPath ('WPF\' + $_ + '.dll'))
}
$references += '/reference:' + (Join-Path $frameworkPath 'System.Web.Extensions.dll')
$references += '/reference:' + (Join-Path $frameworkPath 'System.Xaml.dll')
$sources = @((Join-Path $PSScriptRoot 'XpsIntake.cs'), (Join-Path $PSScriptRoot 'NativeXps.cs'), (Join-Path $PSScriptRoot 'ExposureImage.cs'), (Join-Path $PSScriptRoot 'CorelXpLayout.cs'), (Join-Path $PSScriptRoot 'ColorReviewImage.cs'), (Join-Path $PSScriptRoot 'SemanticColorLayers.cs'))
$executablePath = Join-Path $buildPath 'Aurora.XpsIntake.exe'
if($SemanticCampaign){
    $sources += Join-Path $PSScriptRoot 'SemanticColorCampaign.cs'
    $executablePath = Join-Path $buildPath 'Aurora.SemanticColorCampaign.exe'
    $entryPoint = '/main:Aurora.Frontend.SemanticColorCampaign'
} elseif ($Test) {
    $sources += Join-Path $PSScriptRoot 'XpsIntakeTests.cs'
    $executablePath = Join-Path $buildPath 'Aurora.XpsIntake.Tests.exe'
    $entryPoint = '/main:Aurora.Frontend.IntakeTests'
} else { $entryPoint = '/main:Aurora.Frontend.Program' }
& $compilerPath /nologo /target:exe /platform:x64 /optimize+ /warnaserror+ $entryPoint ('/out:' + $executablePath) @references @sources
if ($LASTEXITCODE -ne 0) { throw 'Frontend compilation failed.' }
if ($Test) {
    $testPath = if ($TestArtifacts) { [IO.Path]::GetFullPath($TestArtifacts) } else { Join-Path $projectRoot 'runtime\frontend-tests' }
    & $executablePath $testPath
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
} else { Write-Output $executablePath }
