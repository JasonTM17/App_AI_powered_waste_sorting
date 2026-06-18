param(
  [double]$Interval = 5,
  [int]$HistoryLimit = 50
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$envFile = Join-Path $root ".env.local"
if (-not (Test-Path -LiteralPath $envFile)) {
  throw "Missing .env.local"
}

$dbLine = Get-Content -LiteralPath $envFile |
  Where-Object { $_ -match "^TRASH_SORTER_SUPABASE_DATABASE_URL=|^TRASH_SORTER_AUTH_DATABASE_URL=" } |
  Select-Object -First 1

if (-not $dbLine) {
  throw "Missing TRASH_SORTER_SUPABASE_DATABASE_URL or TRASH_SORTER_AUTH_DATABASE_URL in .env.local"
}

$env:TRASH_SORTER_SUPABASE_DATABASE_URL = ($dbLine -replace "^[^=]+=", "").Trim().Trim('"').Trim("'")
$env:TRASH_SORTER_DEMO_HARDWARE_TARGET = if ($env:TRASH_SORTER_DEMO_HARDWARE_TARGET) {
  $env:TRASH_SORTER_DEMO_HARDWARE_TARGET
} else {
  "1"
}
$env:PYTHONPATH = $root

python -m uv run python scripts\supabase_hardware_bridge.py --interval $Interval --history-limit $HistoryLimit
