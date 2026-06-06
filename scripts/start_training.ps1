param(
    [int]$Epochs = 100,
    [int]$ImgSize = 640,
    [int]$Batch = 16,
    [string]$Device = "0",
    [string]$Model = "models\best.pt",
    [int]$Patience = 20,
    [int]$Workers = 0,
    [double]$Fraction = 1.0,
    [string]$Name = "trash-sorter-v3",
    [double]$Lr0 = 0.0015,
    [double]$Lrf = 0.01,
    [double]$WarmupEpochs = 2.0,
    [int]$CloseMosaic = 20,
    [string]$Optimizer = "SGD",
    [switch]$CosLr,
    [switch]$ExistOk
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $Root "runs\train_logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir "$Name-$Stamp.log"
$PidPath = Join-Path $LogDir "$Name-$Stamp.pid"

$TrainArgs = @(
    "scripts\train_yolo.py",
    "--device", $Device,
    "--model", $Model,
    "--epochs", "$Epochs",
    "--imgsz", "$ImgSize",
    "--batch", "$Batch",
    "--workers", "$Workers",
    "--patience", "$Patience",
    "--fraction", "$Fraction",
    "--name", $Name,
    "--lr0", "$Lr0",
    "--lrf", "$Lrf",
    "--warmup-epochs", "$WarmupEpochs",
    "--close-mosaic", "$CloseMosaic",
    "--optimizer", $Optimizer
)

if ($CosLr) {
    $TrainArgs += "--cos-lr"
}

if ($ExistOk) {
    $TrainArgs += "--exist-ok"
}

$EscapedRoot = $Root.Replace("'", "''")
$EscapedLog = $LogPath.Replace("'", "''")
$LiteralArgs = ($TrainArgs | ForEach-Object { "'" + $_.Replace("'", "''") + "'" }) -join ", "

$Runner = @"
`$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
`$OutputEncoding = [System.Text.UTF8Encoding]::new()
Set-Location -LiteralPath '$EscapedRoot'
New-Item -ItemType Directory -Force .uv-cache, .tmp | Out-Null
`$env:UV_CACHE_DIR = '$EscapedRoot\.uv-cache'
`$env:TEMP = '$EscapedRoot\.tmp'
`$env:TMP = '$EscapedRoot\.tmp'
`$env:PYTHONIOENCODING = 'utf-8'
`$trainArgs = @($LiteralArgs)
& python -m uv run python @trainArgs *>&1 | Tee-Object -FilePath '$EscapedLog'
`$code = `$LASTEXITCODE
"exit_code=`$code" | Add-Content -Path '$EscapedLog'
exit `$code
"@

$Process = Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -PassThru -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $Runner
)

$Process.Id | Set-Content -Path $PidPath -Encoding ASCII

[pscustomobject]@{
    pid = $Process.Id
    log = $LogPath
    pid_file = $PidPath
    name = $Name
    epochs = $Epochs
    model = $Model
    batch = $Batch
    device = $Device
    lr0 = $Lr0
    lrf = $Lrf
    warmup_epochs = $WarmupEpochs
    close_mosaic = $CloseMosaic
    optimizer = $Optimizer
    cos_lr = [bool]$CosLr
} | ConvertTo-Json -Depth 3
