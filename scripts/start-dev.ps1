$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$serverRoot = Join-Path $repoRoot "server"

Set-Location $serverRoot
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
