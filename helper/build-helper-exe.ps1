$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Installing build tools..."
py -m pip install -U pyinstaller pillow

Write-Host "Building ClipTapHelper.exe..."
py -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name ClipTapHelper `
  --distpath "$ProjectRoot\dist" `
  --workpath "$ProjectRoot\build" `
  "$ScriptDir\ClipTapHelper.pyw"

Write-Host "Done: $ProjectRoot\dist\ClipTapHelper.exe"
