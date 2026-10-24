' Read-only CorelDRAW inspection. Does not print, save/change the drawing,
' change printer settings or start JobServer. Run with test-corel11.cdr open.
Option Explicit
Dim fso, folder, app, doc, report, stamp, failure, shape, i, progID, shapes, x, y, w, h
Set app = Nothing
Set doc = Nothing
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
stamp = Year(Now) & Right("0" & Month(Now),2) & Right("0" & Day(Now),2) & "-" & Right("0" & Hour(Now),2) & Right("0" & Minute(Now),2) & Right("0" & Second(Now),2)
If fso.FileExists(folder & "\xp-artwork-state-" & stamp & ".txt") Then WScript.Quit 1
Set report = fso.CreateTextFile(folder & "\xp-artwork-state-" & stamp & ".txt", False, True)
report.WriteLine "Read-only CorelDRAW state, " & Now
report.WriteLine "Collector version = 2"
progID = "CorelDRAW.Application.11"
If WScript.Arguments.Count > 0 Then progID = WScript.Arguments(0)
On Error Resume Next
Set app = GetObject(, progID)
If Err.Number <> 0 Then
    Err.Clear
    Set app = CreateObject(progID)
End If
failure = Err.Description
Err.Clear
On Error GoTo 0
If app Is Nothing Then
    report.WriteLine "Could not attach to CorelDRAW 11: " & failure
Else
    Emit app, "Version", "Application.Version"
    Emit app, "Documents.Count", "Documents.Count"
    On Error Resume Next
    Set doc = app.ActiveDocument
    Err.Clear
    On Error GoTo 0
    If Not doc Is Nothing Then
        Emit doc, "Name", "Document.Name"
        Emit doc, "FileName", "Document.FileName"
        Emit doc, "FullFileName", "Document.FullFileName"
        Emit doc, "Unit", "Document.Unit"
        Emit doc, "DrawingOriginX", "Document.DrawingOriginX"
        Emit doc, "DrawingOriginY", "Document.DrawingOriginY"
        Emit doc, "ActivePage.LeftX", "Page.LeftX"
        Emit doc, "ActivePage.TopY", "Page.TopY"
        Emit doc, "ActivePage.SizeWidth", "Page.Width"
        Emit doc, "ActivePage.SizeHeight", "Page.Height"
        Emit doc, "PrintSettings.Printer.Name", "Print.Printer"
        Emit doc, "PrintSettings.PaperWidth", "Print.PaperWidth"
        Emit doc, "PrintSettings.PaperHeight", "Print.PaperHeight"
        Emit doc, "PrintSettings.PageMatchingMode", "Print.PageMatchingMode"
        Emit doc, "ActivePage.Shapes.Count", "Page.ShapeCount"
        Emit doc, "ReferencePoint", "Document.ReferencePoint"
        On Error Resume Next
        Set shapes = doc.ActivePage.Shapes
        i = 0
        For Each shape In shapes
            i = i + 1
            Emit shape, "Type", "Shape" & i & ".Type"
            Emit shape, "LeftX", "Shape" & i & ".LeftX"
            Emit shape, "TopY", "Shape" & i & ".TopY"
            Emit shape, "SizeWidth", "Shape" & i & ".Width"
            Emit shape, "SizeHeight", "Shape" & i & ".Height"
            Emit shape, "Outline.Width", "Shape" & i & ".OutlineWidth"
            Emit shape, "PositionX", "Shape" & i & ".PositionX"
            Emit shape, "PositionY", "Shape" & i & ".PositionY"
            Err.Clear
            x = CDbl(0): y = CDbl(0): w = CDbl(0): h = CDbl(0)
            shape.GetBoundingBox x, y, w, h
            If Err.Number = 0 Then
                report.WriteLine "Shape" & i & ".BoundingBox(x,y,w,h) = " & x & ", " & y & ", " & w & ", " & h
            Else
                report.WriteLine "Shape" & i & ".BoundingBox = [unavailable: " & Err.Description & "]"
            End If
            Err.Clear
            If shape.Type = 6 Then
                Emit shape, "Text.Story.Text", "Shape" & i & ".Text"
                Emit shape, "Text.Story.Font", "Shape" & i & ".Font"
                Emit shape, "Text.Story.Size", "Shape" & i & ".FontSize"
            End If
        Next
        If Err.Number <> 0 Then report.WriteLine "Shape enumeration error = " & Err.Description
        report.WriteLine "Enumerated shape count = " & i
        On Error GoTo 0
    Else
        report.WriteLine "No active document. Open test-corel11.cdr, then rerun."
    End If
End If
report.Close
WScript.Echo "Read-only report saved beside this script. Keep JobServer closed and XP offline; tell Codex the report is ready."

Sub Emit(obj, member, label)
    Dim value, errorText
    On Error Resume Next
    Err.Clear
    value = Eval("obj." & member)
    If Err.Number <> 0 Then
        errorText = Err.Description
        report.WriteLine label & " = [unavailable: " & errorText & "]"
    Else
        report.WriteLine label & " = " & CStr(value)
    End If
    Err.Clear
    On Error GoTo 0
End Sub
