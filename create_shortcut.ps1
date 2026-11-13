# 创建桌面快捷方式（A 路线：无黑窗口启动）。
# 用法：  powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
#        加 -UseExe 则指向 PyInstaller 生成的独立 exe（B 路线产物）。
param(
    [switch]$UseExe,
    [string]$ShortcutName = "本地游戏库管理器"
)

$ErrorActionPreference = "Stop"
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$icon = Join-Path $base "assets\app.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop ($ShortcutName + ".lnk")

if ($UseExe) {
    $target = Join-Path $base "dist\本地游戏库管理器.exe"
    if (-not (Test-Path $target)) { throw "未找到 $target，请先运行 build_exe.bat" }
    $targetPath = $target
    $arguments = ""
} else {
    # wscript.exe 运行 launch.vbs，完全不弹控制台
    $vbs = Join-Path $base "launch.vbs"
    if (-not (Test-Path $vbs)) { throw "未找到 launch.vbs" }
    $targetPath = Join-Path $env:WINDIR "System32\wscript.exe"
    $arguments = '"' + $vbs + '"'
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $base
if (Test-Path $icon) { $shortcut.IconLocation = $icon }
$shortcut.Description = "本地游戏库管理器"
$shortcut.Save()

Write-Output ("已创建: " + $lnk)
Write-Output ("指向  : " + $targetPath + " " + $arguments)
