Set-Location -LiteralPath $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  & $python.Source .\server.py
} else {
  & py -3 .\server.py
}
