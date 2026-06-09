param(
    [string]$ClassName = "Pen",
    [Alias("Profile")]
    [ValidateSet("micro", "strong")]
    [string]$TrainProfile = "micro"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "runs\train_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$slug = ($ClassName -replace "[^A-Za-z0-9_-]+", "-").Trim("-").ToLowerInvariant()
if (-not $slug) {
    $slug = "all"
}
$prefix = "learn-now-$TrainProfile-$slug-$timestamp"
$logPath = Join-Path $logDir "$prefix.log"

$seedCandidates = @(
    "runs\train\trash-sorter-common-software-stage2-fast512-b16\weights\best.pt",
    "runs\train\trash-sorter-common-software-stage2\weights\best.pt",
    "runs\train\trash-sorter-v6-pen-hardware-b8\weights\best.pt",
    "models\best.pt"
)
$seedModel = $seedCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $seedModel) {
    throw "Missing seed model. Checked: $($seedCandidates -join ', ')"
}

if ($TrainProfile -eq "strong") {
    $maxImages = 12000
    $legacyQuota = 220
    $stage1Epochs = 12
    $stage2Epochs = 8
    $stage2Batch = 4
    $stage2ImgSize = 640
    $stage2AmpArgs = @("--amp")
} else {
    $maxImages = 7000
    $legacyQuota = 120
    $stage1Epochs = 8
    $stage2Epochs = 6
    $stage2Batch = 4
    $stage2ImgSize = 576
    $stage2AmpArgs = @("--no-amp")
}

$datasetDir = "dataset_v2\yolo_learn_now_$TrainProfile"
$stage1Name = "$prefix-stage1"
$stage2Name = "$prefix-stage2"

Start-Transcript -Path $logPath -Force | Out-Null
try {
    Write-Host "Learn Now train profile: $TrainProfile"
    Write-Host "Focus class: $ClassName"
    Write-Host "Seed model: $seedModel"

    $exportArgs = @(
        "scripts\export_fast_trainset.py",
        "--out", $datasetDir,
        "--max-images", "$maxImages",
        "--legacy-quota", "$legacyQuota",
        "--focus-class", $ClassName,
        "--include-common-waste",
        "--min-box-area", "0.001",
        "--min-box-side", "0.005"
    )
    python -m uv run python @exportArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Learn Now export failed with exit code $LASTEXITCODE"
    }

    python -m uv run python scripts\train_yolo.py `
        --data "$datasetDir\data.yaml" `
        --model $seedModel `
        --epochs $stage1Epochs `
        --imgsz 512 `
        --batch 16 `
        --workers 0 `
        --patience 4 `
        --freeze 10 `
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
        --name $stage1Name
    if ($LASTEXITCODE -ne 0) {
        throw "Learn Now stage1 failed with exit code $LASTEXITCODE"
    }

    $stageOne = "runs\train\$stage1Name\weights\best.pt"
    if (-not (Test-Path $stageOne)) {
        throw "Stage 1 did not produce weights: $stageOne"
    }

    python -m uv run python scripts\train_yolo.py `
        --data "$datasetDir\data.yaml" `
        --model $stageOne `
        --epochs $stage2Epochs `
        --imgsz $stage2ImgSize `
        --batch $stage2Batch `
        --workers 0 `
        --patience 4 `
        --cache-mode none `
        $stage2AmpArgs `
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
        --lr0 0.0006 `
        --name $stage2Name
    if ($LASTEXITCODE -ne 0) {
        throw "Learn Now stage2 failed with exit code $LASTEXITCODE"
    }

    $stageTwo = "runs\train\$stage2Name\weights\best.pt"
    if (Test-Path $stageTwo) {
        python -m uv run python scripts\evaluate_yolo.py `
            --model $stageTwo `
            --data "$datasetDir\data.yaml" `
            --split test `
            --imgsz 640 `
            --device 0 `
            --out "runs\eval\$stage2Name-test.json"
    }

    Write-Host "Candidate only. Do not replace models\best.pt until metrics and camera test pass."
} finally {
    Stop-Transcript | Out-Null
}
