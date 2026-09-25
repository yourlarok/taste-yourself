param(
    [string]$RuntimeRoot = "D:\TasteYourselfData\fashn-runtime",
    [string]$WeightsRoot = "D:\TasteYourselfData\fashn-weights"
)

$ErrorActionPreference = "Stop"
$sourceRoot = Join-Path $RuntimeRoot "fashn-vton-1.5-main"
$python = Join-Path $RuntimeRoot ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $WeightsRoot | Out-Null

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    $archive = Join-Path $RuntimeRoot "source.zip"
    curl.exe -L --fail --retry 3 -o $archive `
        "https://codeload.github.com/fashn-AI/fashn-vton-1.5/zip/refs/heads/main"
    if ($LASTEXITCODE -ne 0) { throw "FASHN source download failed." }
    Expand-Archive -LiteralPath $archive -DestinationPath $RuntimeRoot -Force
}

if (-not (Test-Path -LiteralPath $python)) {
    py -3.11 -m venv (Join-Path $RuntimeRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
}

& $python -m pip install torch==2.4.1 torchvision==0.19.1 `
    --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) { throw "CUDA PyTorch installation failed." }

& $python -m pip install -e $sourceRoot fastapi "uvicorn[standard]" python-multipart `
    "transformers==4.46.3"
if ($LASTEXITCODE -ne 0) { throw "FASHN runtime installation failed." }

$download = @"
from huggingface_hub import hf_hub_download
root = r'$WeightsRoot'
hf_hub_download(repo_id='fashn-ai/fashn-vton-1.5', filename='model.safetensors', local_dir=root)
hf_hub_download(repo_id='fashn-ai/DWPose', filename='yolox_l.onnx', local_dir=root + r'\dwpose')
hf_hub_download(repo_id='fashn-ai/DWPose', filename='dw-ll_ucoco_384.onnx', local_dir=root + r'\dwpose')
"@
& $python -c $download
if ($LASTEXITCODE -ne 0) { throw "FASHN weight download failed." }

& $python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
if ($LASTEXITCODE -ne 0) { throw "CUDA validation failed." }

Write-Output "FASHN Windows runtime is ready."
