param(
    [string]$RuntimeRoot = "D:\TasteYourselfData\fashn-runtime",
    [string]$WeightsRoot = "D:\TasteYourselfData\fashn-weights",
    [int]$Port = 9000,
    [string]$WorkerToken = ""
)

$ErrorActionPreference = "Stop"
$python = Join-Path $RuntimeRoot ".venv\Scripts\python.exe"
$workerRoot = Join-Path $PSScriptRoot "..\workers\fashn_vton"

if (-not (Test-Path -LiteralPath $python)) {
    throw "FASHN runtime is missing. Run scripts/setup-fashn-windows.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $WeightsRoot "model.safetensors"))) {
    throw "FASHN model weights are missing. Run scripts/setup-fashn-windows.ps1 first."
}

$env:FASHN_WEIGHTS_DIR = $WeightsRoot
$env:FASHN_OUTPUT_DIR = Join-Path $RuntimeRoot "worker-outputs"
$env:FASHN_WORKER_TOKEN = $WorkerToken
$env:FASHN_DEVICE = "cuda"
$env:HF_HOME = "D:\TasteYourselfData\hf-cache"

New-Item -ItemType Directory -Force -Path $env:FASHN_OUTPUT_DIR, $env:HF_HOME | Out-Null
Push-Location $workerRoot
try {
    & $python -m uvicorn app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "FASHN worker exited with code $LASTEXITCODE." }
}
finally {
    Pop-Location
}
