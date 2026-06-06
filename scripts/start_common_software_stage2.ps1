$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$seedModel = "runs\train\trash-sorter-common-software-stage1\weights\best.pt"
if (-not (Test-Path $seedModel)) {
    throw "Missing stage1 seed model: $seedModel"
}

python -m uv run python scripts\train_yolo.py `
    --data dataset_v2\yolo_fast_common\data.yaml `
    --model $seedModel `
    --epochs 18 `
    --imgsz 640 `
    --batch 8 `
    --workers 0 `
    --patience 8 `
    --cache-mode disk `
    --amp `
    --no-plots `
    --cos-lr `
    --close-mosaic 0 `
    --mosaic 0.0 `
    --erasing 0.0 `
    --scale 0.25 `
    --lr0 0.001 `
    --name trash-sorter-common-software-stage2

if ($LASTEXITCODE -ne 0) {
    throw "Common software stage2 failed with exit code $LASTEXITCODE"
}

Write-Host "Stage2 candidate only. Evaluate software metrics before promotion."
