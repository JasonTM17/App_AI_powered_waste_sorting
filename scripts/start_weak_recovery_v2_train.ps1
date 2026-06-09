param(
    [int]$Stage1Epochs = 8,
    [int]$Stage2Epochs = 4,
    [int]$MaxImages = 8500,
    [int]$LegacyQuota = 360,
    [switch]$SkipRepair,
    [switch]$BypassTargetGate
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "runs\train_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$prefix = "weak-recovery-v2-$timestamp"
$logPath = Join-Path $logDir "$prefix.log"

$seedCandidates = @(
    "runs\train\learn-now-micro-pen-20260607-073911-stage1\weights\best.pt",
    "runs\train\trash-sorter-common-software-stage2-fast512-b16\weights\best.pt",
    "models\best.pt"
)
$seedModel = $seedCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $seedModel) {
    throw "Missing seed model. Checked: $($seedCandidates -join ', ')"
}

$datasetDir = "dataset_v2\yolo_weak_recovery_v2"
$stage1Name = "$prefix-stage-a"
$stage2Name = "$prefix-stage-b-576-b4-noamp"
$stage1Eval = "runs\eval\$stage1Name-test.json"
$stage2Eval = "runs\eval\$stage2Name-test.json"
$decisionPath = "runs\eval\$prefix-decision.json"
$phase13Baseline = "runs\eval\vietnam-common-strong-pen-20260607-191222-promotion-decision.json"
$phase14Baseline = "runs\eval\weak-recovery-20260607-201051-decision.json"
$baselineEvals = @(
    "runs\eval\learn-now-micro-stage1-test-576.json",
    "runs\eval\learn-now-micro-stage2-576-b4-noamp-r2-test.json",
    "runs\eval\learn-now-seed-common-stage2-fast512-b16-test-576.json"
)

foreach ($requiredPath in @($phase13Baseline, $phase14Baseline)) {
    if (-not (Test-Path $requiredPath)) {
        throw "Missing comparison baseline: $requiredPath"
    }
}

Start-Transcript -Path $logPath -Force | Out-Null
try {
    Write-Host "Phase 15 weak recovery v2 train"
    Write-Host "Seed model: $seedModel"
    Write-Host "Candidate only. Production models\best.pt will not be replaced."

    $auditArgs = @(
        "scripts\audit_weak_recovery_targets.py",
        "--report", "dataset_v2\phase15_weak_recovery_audit.json"
    )
    if (-not $SkipRepair) {
        $auditArgs += "--repair"
    }
    python -m uv run python @auditArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 15 weak target audit failed with exit code $LASTEXITCODE"
    }
    $targetAudit = Get-Content "dataset_v2\phase15_weak_recovery_audit.json" -Raw | ConvertFrom-Json
    $missingTargets = @(
        $targetAudit.classes |
            Where-Object { [int]$_.target_true_bbox -gt 0 -and [int]$_.missing_target -gt 0 } |
            ForEach-Object { "$($_.class_name):$($_.missing_target)" }
    )
    if ($missingTargets.Count -gt 0 -and -not $BypassTargetGate) {
        Write-Warning "Phase 15 target gate failed. Missing true-bbox targets: $($missingTargets -join ', ')"
        Write-Warning "Skipping train. Review/import more true-bbox data or rerun with -BypassTargetGate for a diagnostic-only candidate."
        return
    }

    python -m uv run python scripts\export_weak_recovery_v2_trainset.py `
        --out $datasetDir `
        --max-images $MaxImages `
        --legacy-quota $LegacyQuota `
        --min-box-area 0.001 `
        --min-box-side 0.005
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 export failed with exit code $LASTEXITCODE"
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
        --scale 0.10 `
        --translate 0.04 `
        --hsv-h 0.0 `
        --hsv-s 0.0 `
        --hsv-v 0.0 `
        --fliplr 0.25 `
        --lr0 0.0007 `
        --name $stage1Name
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 Stage A failed with exit code $LASTEXITCODE"
    }

    $stageOne = "runs\train\$stage1Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageOne `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --device 0 `
        --out $stage1Eval
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 Stage A evaluation failed with exit code $LASTEXITCODE"
    }

    $decisionArgs = @("--candidate", $stage1Eval)
    foreach ($baseline in $baselineEvals) {
        if (Test-Path $baseline) {
            $decisionArgs += @("--baseline", $baseline)
        }
    }
    $decisionArgs += @(
        "--weak-baseline", $phase14Baseline,
        "--comparison-baseline", $phase13Baseline,
        "--comparison-baseline", $phase14Baseline,
        "--required-weak-class", "Pen",
        "--required-weak-class", "Disposable tableware",
        "--required-weak-class", "Ceramic",
        "--out", $decisionPath
    )
    python -m uv run python scripts\write_weak_recovery_decision.py @decisionArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 Stage A decision failed with exit code $LASTEXITCODE"
    }
    $stageOneDecision = Get-Content $decisionPath -Raw | ConvertFrom-Json
    if (-not [bool]$stageOneDecision.stage_b_allowed) {
        Write-Warning "Stage A did not pass Phase 15 gates. Skipping Stage B."
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
        --scale 0.08 `
        --translate 0.04 `
        --hsv-h 0.0 `
        --hsv-s 0.0 `
        --hsv-v 0.0 `
        --fliplr 0.25 `
        --lr0 0.00045 `
        --name $stage2Name
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 Stage B failed with exit code $LASTEXITCODE"
    }

    $stageTwo = "runs\train\$stage2Name\weights\best.pt"
    python -m uv run python scripts\evaluate_yolo.py `
        --model $stageTwo `
        --data "$datasetDir\data.yaml" `
        --split test `
        --imgsz 576 `
        --device 0 `
        --out $stage2Eval
    if ($LASTEXITCODE -ne 0) {
        throw "Weak recovery v2 Stage B evaluation failed with exit code $LASTEXITCODE"
    }

    $finalDecisionArgs = @("--candidate", $stage1Eval, "--candidate", $stage2Eval)
    foreach ($baseline in $baselineEvals) {
        if (Test-Path $baseline) {
            $finalDecisionArgs += @("--baseline", $baseline)
        }
    }
    $finalDecisionArgs += @(
        "--weak-baseline", $phase14Baseline,
        "--comparison-baseline", $phase13Baseline,
        "--comparison-baseline", $phase14Baseline,
        "--required-weak-class", "Pen",
        "--required-weak-class", "Disposable tableware",
        "--required-weak-class", "Ceramic",
        "--out", $decisionPath
    )
    python -m uv run python scripts\write_weak_recovery_decision.py @finalDecisionArgs

    Write-Host "Decision: $decisionPath"
    Write-Host "Candidate only. Test camera before any model promotion."
} finally {
    Stop-Transcript | Out-Null
}
