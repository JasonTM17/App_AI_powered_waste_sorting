$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$seedModel = "runs\train\trash-sorter-v6-pen-hardware-b8\weights\best.pt"
if (-not (Test-Path $seedModel)) {
    throw "Missing V6 seed model: $seedModel"
}

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

python -m uv run python scripts\export_fast_trainset.py `
    --out dataset_v2\yolo_fast_common `
    --max-images 6000 `
    --legacy-quota 120 `
    --include-common-waste `
    --min-box-area 0.001 `
    --min-box-side 0.005
Assert-LastExitCode "Export common software trainset"

python -m uv run python scripts\train_yolo.py `
    --data dataset_v2\yolo_fast_common\data.yaml `
    --model $seedModel `
    --epochs 30 `
    --imgsz 640 `
    --batch 8 `
    --workers 0 `
    --patience 12 `
    --cache-mode disk `
    --amp `
    --no-plots `
    --cos-lr `
    --close-mosaic 5 `
    --mosaic 0.0 `
    --erasing 0.0 `
    --scale 0.25 `
    --lr0 0.002 `
    --name trash-sorter-common-software-stage1
Assert-LastExitCode "Common software training"

Write-Host "Candidate only. Evaluate software metrics before promotion."
