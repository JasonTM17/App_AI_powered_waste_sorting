param(
    [int]$Stage1Epochs = 6,
    [int]$Stage2Epochs = 4,
    [int]$MaxImages = 12000,
    [int]$LegacyQuota = 1200
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$prefix = "kaggle-real-image-v5-$timestamp"
$logDir = Join-Path $root "runs\train_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "$prefix.log"

$seedCandidates = @(
    "runs\train\learn-now-micro-pen-20260607-073911-stage1\weights\best.pt",
    "models\best.pt"
)
$seedModel = $seedCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $seedModel) {
    throw "Missing seed model. Checked: $($seedCandidates -join ', ')"
}

$datasetDir = "dataset_v2\yolo_kaggle_real_image_v5"
$stage1Name = "$prefix-stage-a"
$stage2Name = "$prefix-stage-b-576-b4-noamp"
$stage1Eval = "runs\eval\$stage1Name-test.json"
$stage2Eval = "runs\eval\$stage2Name-test.json"
$decisionPath = "runs\eval\$prefix-decision.json"
$weakBaseline = "runs\eval\weak-recovery-v2-20260607-212254-decision.json"
$comparisonBaselines = @(
    "runs\eval\weak-recovery-20260607-201051-decision.json",
    "runs\eval\weak-recovery-v2-20260607-212254-decision.json"
)
$baselineEvals = @(
    "runs\eval\learn-now-micro-stage1-test-576.json",
    "runs\eval\learn-now-micro-stage2-576-b4-noamp-r2-test.json",
    "runs\eval\learn-now-seed-common-stage2-fast512-b16-test-576.json"
)

if (-not (Test-Path $weakBaseline)) {
    throw "Missing weak baseline decision: $weakBaseline"
}

Start-Transcript -Path $logPath -Force | Out-Null
try {
    Write-Host "Phase 20 Kaggle real-image v5 train"
    Write-Host "Seed model: $seedModel"
    Write-Host "Candidate only. Hardware dispatch remains deferred."

    python -m uv run python scripts\export_kaggle_real_image_trainset.py `
        --out $datasetDir `
        --max-images $MaxImages `
        --legacy-quota $LegacyQuota `
        --min-box-area 0.001 `
        --min-box-side 0.005
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle real-image v5 export failed with exit code $LASTEXITCODE"
    }

    python -m uv run python scripts\train_yolo.py `
        --data "$datasetDir\data.yaml" `
        --model $seedModel `
        --epochs $Stage1Epochs `
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
        --scale 0.08 `
        --translate 0.04 `
        --hsv-h 0.0 `
        --hsv-s 0.0 `
        --hsv-v 0.0 `
        --fliplr 0.25 `
        --lr0 0.0006 `
        --name $stage1Name
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle Stage A failed with exit code $LASTEXITCODE"
    }

    $stageOne = "runs\train\$stage1Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageOne `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --batch 4 `
        --workers 0 `
        --max-det 100 `
        --device 0 `
        --out $stage1Eval
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle Stage A evaluation failed with exit code $LASTEXITCODE"
    }

    $decisionArgs = @("--candidate", $stage1Eval)
    foreach ($baseline in $baselineEvals) {
        if (Test-Path $baseline) {
            $decisionArgs += @("--baseline", $baseline)
        }
    }
    $decisionArgs += @(
        "--weak-baseline", $weakBaseline,
        "--required-weak-class", "Pen",
        "--required-weak-class", "Disposable tableware",
        "--required-weak-class", "Textile",
        "--required-recall-class", "Disposable tableware",
        "--required-recall-class", "Textile",
        "--min-required-recall", "0.05",
        "--out", $decisionPath
    )
    foreach ($baseline in $comparisonBaselines) {
        if (Test-Path $baseline) {
            $decisionArgs += @("--comparison-baseline", $baseline)
        }
    }
    python -m uv run python scripts\write_weak_recovery_decision.py @decisionArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle Stage A decision failed with exit code $LASTEXITCODE"
    }
    $stageOneDecision = Get-Content $decisionPath -Raw | ConvertFrom-Json
    if (-not [bool]$stageOneDecision.stage_b_allowed) {
        Write-Warning "Stage A did not pass Phase 20 gates. Skipping Stage B."
        Write-Host "Decision: $decisionPath"
        return
    }

    python -m uv run python scripts\train_yolo.py `
        --data "$datasetDir\data.yaml" `
        --model $stageOne `
        --epochs $Stage2Epochs `
        --imgsz 576 `
        --batch 4 `
        --workers 0 `
        --patience 4 `
        --cache-mode none `
        --no-amp `
        --no-plots `
        --cos-lr `
        --close-mosaic 0 `
        --mosaic 0.0 `
        --erasing 0.0 `
        --scale 0.06 `
        --translate 0.03 `
        --hsv-h 0.0 `
        --hsv-s 0.0 `
        --hsv-v 0.0 `
        --fliplr 0.25 `
        --lr0 0.00035 `
        --name $stage2Name
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle Stage B failed with exit code $LASTEXITCODE"
    }

    $stageTwo = "runs\train\$stage2Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageTwo `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --batch 4 `
        --workers 0 `
        --max-det 100 `
        --device 0 `
        --out $stage2Eval
    if ($LASTEXITCODE -ne 0) {
        throw "Kaggle Stage B evaluation failed with exit code $LASTEXITCODE"
    }

    $finalDecisionArgs = @("--candidate", $stage1Eval, "--candidate", $stage2Eval)
    foreach ($baseline in $baselineEvals) {
        if (Test-Path $baseline) {
            $finalDecisionArgs += @("--baseline", $baseline)
        }
    }
    $finalDecisionArgs += @(
        "--weak-baseline", $weakBaseline,
        "--required-weak-class", "Pen",
        "--required-weak-class", "Disposable tableware",
        "--required-weak-class", "Textile",
        "--required-recall-class", "Disposable tableware",
        "--required-recall-class", "Textile",
        "--min-required-recall", "0.05",
        "--out", $decisionPath
    )
    foreach ($baseline in $comparisonBaselines) {
        if (Test-Path $baseline) {
            $finalDecisionArgs += @("--comparison-baseline", $baseline)
        }
    }
    python -m uv run python scripts\write_weak_recovery_decision.py @finalDecisionArgs
    Write-Host "Decision: $decisionPath"
    Write-Host "Candidate only. Test camera before any model promotion."
} finally {
    Stop-Transcript | Out-Null
}
