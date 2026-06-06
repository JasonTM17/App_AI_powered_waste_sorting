$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$seedModel = "runs\train\trash-sorter-v6-pen-hardware-b8\weights\best.pt"
if (-not (Test-Path $seedModel)) {
    throw "Missing V6 seed model: $seedModel"
}

python -m uv run python scripts\export_fast_trainset.py `
    --out dataset_v2\yolo_fast_common `
    --max-images 6000 `
    --legacy-quota 120 `
    --include-common-waste `
    --min-box-area 0.001 `
    --min-box-side 0.005

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
    --lr0 0.002 `
    --name trash-sorter-common-software-stage1

Write-Host "Candidate only. Evaluate software metrics before promotion."
