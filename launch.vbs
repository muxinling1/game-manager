' Launch the local game manager with NO console window.
' Reads the interpreter recorded by setup.bat, swaps python.exe -> pythonw.exe,
' and runs "pythonw -m src.webapp" with the project folder as working dir.
Option Explicit
Dim sh, fso, base, runtimeFile, py, pyw, cmd, ts, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)

runtimeFile = base & "\vendor\runtime.txt"
If Not fso.FileExists(runtimeFile) Then
    MsgBox "Dependencies not installed. Run setup.bat once first.", 16, "Local Game Manager"
    WScript.Quit 1
End If

Set ts = fso.OpenTextFile(runtimeFile, 1)
py = Trim(ts.ReadLine)
ts.Close
pyw = Replace(py, "python.exe", "pythonw.exe")
If Not fso.FileExists(pyw) Then pyw = py

sh.CurrentDirectory = base
cmd = """" & pyw & """ -m src.webapp"
rc = sh.Run(cmd, 0, True)
If rc <> 0 Then
    Dim log
    Set log = fso.CreateTextFile(base & "\launch-error.log", True)
    log.WriteLine "Exit code: " & rc
    log.WriteLine "Command:   " & cmd
    log.Close
    MsgBox "Failed to start (exit " & rc & "). See launch-error.log", 16, "Local Game Manager"
End If
