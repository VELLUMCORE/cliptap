$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$AssetsDir = Join-Path $ScriptDir "assets"
$IcoIcon = Join-Path $AssetsDir "ClipTapHelper.ico"

Write-Host "Installing build tools..."
py -m pip install -U pyinstaller yt-dlp pillow

Write-Host "Building standalone ClipTapHelper.exe..."
$PyInstallerArgs = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--name", "ClipTapHelper",
  "--distpath", "$ProjectRoot\dist",
  "--workpath", "$ProjectRoot\build",
  "--specpath", "$ProjectRoot\build",
  "--icon", $IcoIcon,
  "--collect-all", "yt_dlp",
  "$ScriptDir\ClipTapHelper.py"
)

py -m PyInstaller @PyInstallerArgs

Write-Host "Done: $ProjectRoot\dist\ClipTapHelper.exe"
