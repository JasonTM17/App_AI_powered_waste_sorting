param(
    [string]$Log,
    [string]$Name,
    [int]$Tail = 40
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $Root "runs\train_logs"

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*scripts\train_yolo.py*" -and
        $_.CommandLine -notlike "*Where-Object*scripts\train_yolo.py*"
    } |
    Select-Object ProcessId, Name, CommandLine

if (-not $Log) {
    $Latest = Get-ChildItem -Path $LogDir -Filter "*.log" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($Latest) {
        $Log = $Latest.FullName
    }
}

if (-not $Name) {
    $Active = @($Processes | Select-Object -First 1)
    if ($Active -and $Active.CommandLine -match "--name\s+([^\s]+)") {
        $Name = $Matches[1]
    } elseif ($Log) {
        $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($Log)
        $Name = $BaseName -replace "-\d{8}-\d{6}$", ""
    } else {
        $Name = "trash-sorter-v3"
    }
}

[pscustomobject]@{
    running = @($Processes).Count -gt 0
    processes = @($Processes)
    log = $Log
    run = $Name
} | ConvertTo-Json -Depth 4

$ResultsCsv = Join-Path $Root "runs\train\$Name\results.csv"
if (Test-Path $ResultsCsv) {
    $Rows = @(Import-Csv -Path $ResultsCsv)
    if ($Rows.Count -gt 0) {
        "`n--- latest metrics: $ResultsCsv ---"
        $Rows[-1] | ConvertTo-Json -Depth 4
    }
}

if ($Log -and (Test-Path $Log)) {
    "`n--- log tail: $Log ---"
    Get-Content -Path $Log -Tail $Tail
}
