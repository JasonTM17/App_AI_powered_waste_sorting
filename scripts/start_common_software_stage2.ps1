$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$seedCandidates = @(
    "runs\train\trash-sorter-common-software-stage2\weights\best.pt",
    "runs\train\trash-sorter-common-software-stage1\weights\best.pt"
)
$seedModel = $seedCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $seedModel) {
    throw "Missing stage seed model. Checked: $($seedCandidates -join ', ')"
}

python -m uv run python scripts\train_yolo.py `
    --data dataset_v2\yolo_fast_common\data.yaml `
    --model $seedModel `
    --epochs 10 `
    --imgsz 512 `
    --batch 16 `
    --workers 0 `
    --patience 4 `
    --cache-mode none `
    --amp `
    --no-plots `
    --cos-lr `
    --close-mosaic 0 `
    --mosaic 0.0 `
    --erasing 0.0 `
    --scale 0.12 `
    --translate 0.05 `
    --hsv-h 0.0 `
    --hsv-s 0.0 `
    --hsv-v 0.0 `
    --fliplr 0.3 `
    --lr0 0.0008 `
    --name trash-sorter-common-software-stage2-fast512-b16

if ($LASTEXITCODE -ne 0) {
    throw "Common software stage2 fast512 run failed with exit code $LASTEXITCODE"
}

Write-Host "Stage2 candidate only. Evaluate software metrics before promotion."
