param([string]$Destination, [switch]$RasterFills)
$ErrorActionPreference='Stop'
$taskProjectRoot=Split-Path -Parent $PSScriptRoot
if(-not $Destination){
    $taskFolder=if($RasterFills){'color-raster-preferences-20261019'}else{'color-preferences-20261019'}
    $Destination=Join-Path $taskProjectRoot ('reference\artwork\'+$taskFolder)
}
$taskDestination=[IO.Path]::GetFullPath($Destination)
if(Test-Path -LiteralPath $taskDestination){throw 'Choose a new reference directory; existing artifacts are preserved.'}
New-Item -ItemType Directory -Path $taskDestination | Out-Null
$taskFilename=if($RasterFills){'color-raster-reference-corel11.cdr'}else{'color-reference-corel11.cdr'}
$taskOutput=Join-Path $taskDestination $taskFilename
$taskApp=New-Object -ComObject 'CorelDRAW.Application.17'
$taskPrevious=$taskApp.ActiveDocument
$taskDocument=$null
$taskReopened=$null
function Read-ColorReference($document){
    $items=@()
    for($i=1;$i -le $document.ActivePage.Shapes.Count;$i++){
        $s=$document.ActivePage.Shapes.Item($i)
        $item=[ordered]@{Name=[string]$s.Name;Type=[int]$s.Type;Left=[double]$s.LeftX;Top=[double]$s.TopY;
            Width=[double]$s.SizeWidth;Height=[double]$s.SizeHeight;FillType=[int]$s.Fill.Type;
            OutlineWidth=[double]$s.Outline.Width}
        if($s.Name -eq 'RasterBlack' -or $RasterFills){
            $item.FillRgb=@([int]$s.Fill.UniformColor.RGBRed,[int]$s.Fill.UniformColor.RGBGreen,[int]$s.Fill.UniformColor.RGBBlue)
        }else{
            $item.OutlineRgb=@([int]$s.Outline.Color.RGBRed,[int]$s.Outline.Color.RGBGreen,[int]$s.Outline.Color.RGBBlue)
        }
        $items += [pscustomobject]$item
    }
    [pscustomobject]@{Unit=[int]$document.Unit;PageWidth=[double]$document.ActivePage.SizeWidth;
        PageHeight=[double]$document.ActivePage.SizeHeight;Shapes=$items}
}
try{
    # Application document API only: no print call, printer settings or owner file edits.
    $taskDocument=$taskApp.CreateDocument()
    $taskDocument.Unit=1
    $taskDocument.ActivePage.SetSize(30,18)
    $taskDocument.DrawingOriginX=0
    $taskDocument.DrawingOriginY=0
    $taskLeft=[double]$taskDocument.ActivePage.LeftX
    $taskTop=[double]$taskDocument.ActivePage.TopY
    $taskLayer=$taskDocument.ActiveLayer
    $s=$taskLayer.CreateRectangle2($taskLeft+1,$taskTop-1.125,.125,.125)
    $s.Name='RasterBlack'
    $s.Fill.ApplyUniformFill($taskApp.CreateRGBColor(0,0,0))
    $s.Outline.SetNoOutline()
    $specs=@(
        @{Name='Blue1';X=1.0;Rgb=@(0,0,255)},
        @{Name='Red1';X=1.5;Rgb=@(255,0,0)},
        @{Name='Blue2';X=2.0;Rgb=@(0,0,255)},
        @{Name='Red2';X=2.5;Rgb=@(255,0,0)},
        @{Name='UnmatchedOrange';X=3.0;Rgb=@(255,128,0)}
    )
    foreach($spec in $specs){
        $taskSide=if($RasterFills){.125}else{.25}
        $s=$taskLayer.CreateRectangle2($taskLeft+$spec.X,$taskTop-1.5-$taskSide,$taskSide,$taskSide)
        $s.Name=$spec.Name
        if($RasterFills){
            $s.Fill.ApplyUniformFill($taskApp.CreateRGBColor($spec.Rgb[0],$spec.Rgb[1],$spec.Rgb[2]))
            $s.Outline.SetNoOutline()
        }else{
            $s.Fill.ApplyNoFill()
            $s.Outline.Width=.003
            $s.Outline.Color.RGBAssign($spec.Rgb[0],$spec.Rgb[1],$spec.Rgb[2])
        }
    }
    $taskBefore=Read-ColorReference $taskDocument
    if($taskBefore.Unit -ne 1 -or $taskBefore.PageWidth -ne 30 -or $taskBefore.PageHeight -ne 18 -or $taskBefore.Shapes.Count -ne 6){throw 'Unexpected sample document dimensions or shape count.'}
    $taskOptions=$taskApp.CreateStructSaveAsOptions()
    $taskOptions.Version=11
    $taskOptions.Overwrite=$false
    $taskDocument.SaveAs($taskOutput,$taskOptions)
    $taskDocument.Close()
    $taskDocument=$null
    $taskReopened=$taskApp.OpenDocument($taskOutput)
    $taskAfter=Read-ColorReference $taskReopened
    $taskSame=($taskBefore | ConvertTo-Json -Depth 8 -Compress) -ceq ($taskAfter | ConvertTo-Json -Depth 8 -Compress)
    $taskReport=[ordered]@{State='prepared_offline_color_reference';SavedVersion=11;
        SampleKind=$(if($RasterFills){'filled-raster-colors'}else{'vector-colors-with-black-raster-marker'});
        CdrSha256=(Get-FileHash -LiteralPath $taskOutput -Algorithm SHA256).Hash.ToLowerInvariant();
        GeometryAndColorsPreserved=$taskSame;DrawCreationOrder=@('RasterBlack','Blue1','Red1','Blue2','Red2','UnmatchedOrange');
        Before=$taskBefore;After=$taskAfter;PrintSubmitted=$false;PrinterSettingsChanged=$false;PhysicalDeviceIo=$false}
    $taskReport | ConvertTo-Json -Depth 10 | Out-File -LiteralPath (Join-Path $taskDestination 'corel11-document-verification.json') -Encoding utf8 -NoClobber
    if(-not $taskSame){throw 'Corel 11 save/reopen changed the sample; inspect the report before use.'}
    Write-Output ('Saved and verified CorelDRAW 11 document: '+$taskOutput)
}finally{
    if($null -ne $taskReopened){$taskReopened.Close()}
    if($null -ne $taskDocument -and -not $taskDocument.Dirty){$taskDocument.Close()}
    if($null -ne $taskPrevious){$taskPrevious.Activate()}
}
