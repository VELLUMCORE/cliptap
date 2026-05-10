$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Start-Process -FilePath "pyw" -ArgumentList "`"$ScriptDir\ClipTapHelper.pyw`""
