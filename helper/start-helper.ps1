$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
<<<<<<< HEAD
Start-Process -FilePath "pyw" -ArgumentList "`"$ScriptDir\ClipTapHelper.pyw`""
=======
Set-Location $ScriptDir
py .\ClipTapHelper.py --open
>>>>>>> 8059d7f (feat: add standalone web manager build)
