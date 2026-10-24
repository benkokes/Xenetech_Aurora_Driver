' Offline XP file capture only. Never prints, launches programs or sends jobs.
' CANDIDATE is not success: host verification must decode the entire file.
Option Explicit
Const MaxBytes=67108864
Dim fs, root, svc, label, lastLabel, signature, stable, previous, current
Dim started, request, re, target, source, beforeStamp, data
Set fs=CreateObject("Scripting.FileSystemObject")

' Bounded single-file copy for host fixture tests. No WMI, printer or networking.
If WScript.Arguments.Count=3 Then
 If WScript.Arguments(0)="--snapshot" Then
  data=ReadComplete(WScript.Arguments(1))
  If IsEmpty(data) Then WScript.Echo "INCOMPLETE":WScript.Quit 2
  WScript.Sleep 1000
  If Not SameBytes(data,ReadComplete(WScript.Arguments(1))) Then WScript.Echo "CHANGING":WScript.Quit 2
  If Not SaveCandidate(WScript.Arguments(2),data) Then WScript.Echo "COPY FAILED; preserve existing files":WScript.Quit 4
  WScript.Echo "CANDIDATE ONLY; host decode required":WScript.Quit 0
 End If
End If
If WScript.Arguments.Count<>0 Then WScript.Quit 1

root=fs.GetParentFolderName(WScript.ScriptFullName)
source="C:\xfiles\etherin\Default.jbs"
Set svc=GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")
Set re=New RegExp:re.Pattern="^[a-z0-9-]{1,48}$"
lastLabel="":signature="":stable="":previous=Empty:started=Now
Do While DateDiff("s",started,Now)<1800
 If fs.FileExists(root & "\stop-collector.txt") Then Exit Do
 CheckOffline
 If fs.FileExists(root & "\request.txt") Then
  Set request=fs.OpenTextFile(root & "\request.txt",1,False)
  label=Trim(request.ReadAll):request.Close
  If Not re.Test(label) Then Block "invalid label"
  target=root & "\" & label & "\candidate.jbs"
  If label<>lastLabel Then
   If Not fs.FolderExists(root & "\" & label) Then Block "destination directory absent"
   If fs.FileExists(target) Or fs.FileExists(root & "\" & label & "\Default.jbs") Or fs.FileExists(root & "\" & label & "\verified.json") Then Block "destination already used"
   lastLabel=label:signature=Stamp(source):stable="":previous=Empty
   WriteStatus "ARMED " & label
  End If
  current=Stamp(source)
  If signature<>"COPIED" And current<>"" And current<>signature Then
   beforeStamp=current:data=ReadComplete(source)
   If IsEmpty(data) Or Stamp(source)<>beforeStamp Then
    stable="":previous=Empty
   ElseIf current=stable And SameBytes(previous,data) Then
    CheckOffline
    If Not SaveCandidate(target,data) Then Block "candidate copy failed; preserve existing files"
    signature="COPIED":previous=Empty
    WriteStatus "CANDIDATE " & label
   Else
    stable=current:previous=data
   End If
  ElseIf signature<>"COPIED" Then
   stable="":previous=Empty
  End If
 End If
 WScript.Sleep 1000
Loop
WriteStatus "STOPPED"

Function ReadComplete(path)
 Dim stream, bytes, length, index, ending
 ReadComplete=Empty
 On Error Resume Next
 If Not fs.FileExists(path) Then Exit Function
 length=fs.GetFile(path).Size
 If Err.Number<>0 Or length<14 Or length>MaxBytes Then Err.Clear:Exit Function
 Set stream=CreateObject("ADODB.Stream"):stream.Type=1:stream.Open
 stream.LoadFromFile path
 If Err.Number<>0 Then Err.Clear:stream.Close:Exit Function
 If stream.Size<>length Or stream.Size>MaxBytes Then stream.Close:Exit Function
 bytes=stream.Read:stream.Close
 If Err.Number<>0 Then Err.Clear:Exit Function
 On Error GoTo 0
 If AscB(MidB(bytes,1,1))<>33 Or AscB(MidB(bytes,2,1))<>90 Or AscB(MidB(bytes,3,1))<>88 Or AscB(MidB(bytes,4,1))<>13 Then Exit Function
 ending=vbCr & "END_PLOT" & vbCr
 For index=1 To Len(ending)
  If AscB(MidB(bytes,length-Len(ending)+index,1))<>Asc(Mid(ending,index,1)) Then Exit Function
 Next
 ReadComplete=bytes
End Function

Function SameBytes(a,b)
 Dim index
 SameBytes=False
 If IsEmpty(a) Or IsEmpty(b) Then Exit Function
 If LenB(a)<>LenB(b) Then Exit Function
 ' Byte arrays coerce to binary BSTRs. Compare complete UTF-16 pairs using
 ' binary comparison, then explicitly compare an odd final byte as well.
 index=LenB(a)-(LenB(a) Mod 2)
 If StrComp(MidB(a,1,index),MidB(b,1,index),0)<>0 Then Exit Function
 If LenB(a) Mod 2<>0 Then
  If AscB(MidB(a,LenB(a),1))<>AscB(MidB(b,LenB(b),1)) Then Exit Function
 End If
 SameBytes=True
End Function

Function SaveCandidate(path,bytes)
 Dim stream
 SaveCandidate=False
 If fs.FileExists(path) Then Exit Function
 On Error Resume Next
 Set stream=CreateObject("ADODB.Stream"):stream.Type=1:stream.Open
 stream.Write bytes
 If Err.Number=0 Then stream.SaveToFile path,1
 If Err.Number=0 Then SaveCandidate=True
 Err.Clear:stream.Close
 On Error GoTo 0
End Function

Function Stamp(path)
 Dim item
 Stamp=""
 On Error Resume Next
 Set item=fs.GetFile(path)
 If Err.Number=0 Then Stamp=CStr(item.DateLastModified) & ";" & item.Size
 Err.Clear
 On Error GoTo 0
End Function

Sub CheckOffline()
 If svc.ExecQuery("SELECT Name FROM Win32_Process WHERE Name='JobServer.exe'").Count<>0 Then Block "XP JobServer is running"
 If svc.ExecQuery("SELECT Name FROM Win32_NetworkAdapter WHERE NetConnectionStatus=2").Count<>0 Then Block "network adapter connected"
End Sub

Sub Block(reason)
 WriteStatus "BLOCKED: " & reason
 WScript.Quit 3
End Sub

Sub WriteStatus(value)
 Dim log
 Set log=fs.CreateTextFile(root & "\collector-status.txt",True,False)
 log.WriteLine value:log.Close
 Set log=fs.OpenTextFile(root & "\collector-events.txt",8,True)
 log.WriteLine Now & " " & value:log.Close
End Sub
