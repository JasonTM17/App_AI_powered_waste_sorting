$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$seedModel = "runs\train\trash-sorter-v6-pen-hardware-b8\weights\best.pt"
if (-not (Test-Path $seedModel)) {
    throw "Missing V6 seed model: $seedModel"
}

python -m uv run python scripts\export_fast_trainset.py `
    --out dataset_v2\yolo_fast_pen `
    --max-images 4500 `
    --legacy-quota 75

python -m uv run python scripts\train_yolo.py `
    --data dataset_v2\yolo_fast_pen\data.yaml `
    --model $seedModel `
    --epochs 12 `
    --imgsz 512 `
    --batch 8 `
    --workers 0 `
    --patience 5 `
    --freeze 10 `
    --cache-mode disk `
    --amp `
    --name trash-sorter-pen-fast-stage1

$stageOne = "runs\train\trash-sorter-pen-fast-stage1\weights\best.pt"
if (-not (Test-Path $stageOne)) {
    throw "Stage 1 did not produce weights: $stageOne"
}

python -m uv run python scripts\train_yolo.py `
    --data dataset_v2\yolo_fast_pen\data.yaml `
    --model $stageOne `
    --epochs 8 `
    --imgsz 640 `
    --batch 8 `
    --workers 0 `
    --patience 5 `
    --cache-mode disk `
    --amp `
    --name trash-sorter-pen-fast-stage2

Write-Host "Candidate only. Evaluate camera and metrics before promotion."
