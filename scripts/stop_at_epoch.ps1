param(
    [string]$Name = "trash-sorter-v5-low-lr-sgd",
    [int]$TargetEpoch = 50,
    [int]$PollSeconds = 30
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ResultsCsv = Join-Path $Root "runs\train\$Name\results.csv"
$LogDir = Join-Path $Root "runs\train_logs"
$MonitorLog = Join-Path $LogDir "$Name-stop-at-epoch-$TargetEpoch.log"

New-Item -ItemType Directory -Force $LogDir | Out-Null
"$(Get-Date -Format o) monitor started target_epoch=$TargetEpoch results=$ResultsCsv" |
    Add-Content -Path $MonitorLog -Encoding UTF8

while ($true) {
    $Processes = @(
        Get-CimInstance Win32_Process |
            Where-Object { $_.CommandLine -like "*scripts\train_yolo.py*" }
    )

    if ($Processes.Count -eq 0) {
        "$(Get-Date -Format o) no training process is running; monitor exits" |
            Add-Content -Path $MonitorLog -Encoding UTF8
        exit 0
    }

    if (Test-Path $ResultsCsv) {
        try {
            $Rows = @(Import-Csv -Path $ResultsCsv)
            if ($Rows.Count -gt 0) {
                $LatestEpoch = [int]$Rows[-1].epoch
                $DisplayEpoch = $LatestEpoch + 1
                "$(Get-Date -Format o) latest_epoch=$LatestEpoch display_epoch=$DisplayEpoch" |
                    Add-Content -Path $MonitorLog -Encoding UTF8

                if ($DisplayEpoch -ge $TargetEpoch) {
                    "$(Get-Date -Format o) target reached; stopping training processes" |
                        Add-Content -Path $MonitorLog -Encoding UTF8
                    & (Join-Path $PSScriptRoot "stop_training.ps1") |
                        Add-Content -Path $MonitorLog -Encoding UTF8
                    exit 0
                }
            }
        } catch {
            "$(Get-Date -Format o) read failed: $($_.Exception.Message)" |
                Add-Content -Path $MonitorLog -Encoding UTF8
        }
    } else {
        "$(Get-Date -Format o) waiting for results csv" |
            Add-Content -Path $MonitorLog -Encoding UTF8
    }

    Start-Sleep -Seconds $PollSeconds
}
