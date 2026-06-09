param(
    [string]$FocusClass = "Pen",
    [switch]$BypassReadinessGate,
    [int]$Stage1Epochs = 8,
    [int]$Stage2Epochs = 4
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "runs\train_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$slug = ($FocusClass -replace "[^A-Za-z0-9_-]+", "-").Trim("-").ToLowerInvariant()
if (-not $slug) {
    $slug = "all"
}
$prefix = "vietnam-common-strong-$slug-$timestamp"
$logPath = Join-Path $logDir "$prefix.log"

$seedCandidates = @(
    "runs\train\learn-now-micro-pen-20260607-073911-stage1\weights\best.pt",
    "runs\train\trash-sorter-common-software-stage2-fast512-b16\weights\best.pt",
    "runs\train\trash-sorter-v6-pen-hardware-b8\weights\best.pt",
    "models\best.pt"
)
$seedModel = $seedCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $seedModel) {
    throw "Missing seed model. Checked: $($seedCandidates -join ', ')"
}

$datasetDir = "dataset_v2\yolo_strong_vietnam_common_v1"
$stage1Name = "$prefix-stage1"
$stage2Name = "$prefix-stage2-576-b4-noamp"
$stage1Eval = "runs\eval\$stage1Name-test.json"
$stage2Eval = "runs\eval\$stage2Name-test.json"
$decisionPath = "runs\eval\$prefix-promotion-decision.json"
$baselineEvals = @(
    "runs\eval\learn-now-micro-stage1-test-576.json",
    "runs\eval\learn-now-micro-stage2-576-b4-noamp-r2-test.json",
    "runs\eval\learn-now-seed-common-stage2-fast512-b16-test-576.json"
)

Start-Transcript -Path $logPath -Force | Out-Null
try {
    Write-Host "Phase 8 Vietnam common strong train"
    Write-Host "Focus class for readiness gate: $FocusClass"
    Write-Host "Seed model: $seedModel"
    Write-Host "Candidate only. Production models\best.pt will not be replaced."

    python -m uv run python scripts\audit_phase9_readiness.py
    if ($LASTEXITCODE -ne 0) {
        if (-not $BypassReadinessGate) {
            throw "Phase 9 readiness audit failed. Add/review P0 data before strong training, or rerun with -BypassReadinessGate for a candidate-only train."
        }
        Write-Warning "Bypassing Phase 9 readiness gate by explicit operator request. Candidate-only train; do not promote without camera validation."
    }

    python -m uv run python scripts\export_vietnam_common_strong_trainset.py `
        --out $datasetDir `
        --max-images 14000 `
        --legacy-quota 220 `
        --min-box-area 0.001 `
        --min-box-side 0.005 `
        --generated-cap-ratio 0
    if ($LASTEXITCODE -ne 0) {
        throw "Vietnam strong export failed with exit code $LASTEXITCODE"
    }

    python -m uv run python scripts\train_yolo.py `
        --data "$datasetDir\data.yaml" `
        --model $seedModel `
        --epochs $Stage1Epochs `
        --imgsz 512 `
        --batch 16 `
        --workers 0 `
        --patience 5 `
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
        throw "Vietnam strong stage1 failed with exit code $LASTEXITCODE"
    }

    $stageOne = "runs\train\$stage1Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageOne `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --device 0 `
        --out $stage1Eval

    $decisionArgs = @("--candidate", $stage1Eval)
    foreach ($baseline in $baselineEvals) {
        $decisionArgs += @("--baseline", $baseline)
    }
    $decisionArgs += @("--out", $decisionPath)
    python -m uv run python scripts\write_vietnam_common_promotion_decision.py @decisionArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Vietnam strong Stage A decision failed with exit code $LASTEXITCODE"
    }
    $stageOneDecision = Get-Content $decisionPath -Raw | ConvertFrom-Json
    if (-not [bool]$stageOneDecision.regression_gate.passed) {
        Write-Warning "Stage A regressed against the best baseline. Skipping Stage B; keep production model unchanged."
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
        --patience 5 `
        --cache-mode none `
        --no-amp `
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
        throw "Vietnam strong stage2 failed with exit code $LASTEXITCODE"
    }

    $stageTwo = "runs\train\$stage2Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageTwo `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --device 0 `
        --out $stage2Eval

    $decisionArgs = @("--candidate", $stage1Eval, "--candidate", $stage2Eval)
    foreach ($baseline in $baselineEvals) {
        $decisionArgs += @("--baseline", $baseline)
    }
    $decisionArgs += @("--out", $decisionPath)
    python -m uv run python scripts\write_vietnam_common_promotion_decision.py `
        @decisionArgs

    Write-Host "Decision: $decisionPath"
    Write-Host "Candidate only. Test camera before any model promotion."
} finally {
    Stop-Transcript | Out-Null
}
