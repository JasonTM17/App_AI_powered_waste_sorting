param(
    [int]$TrainingPid
)

$ErrorActionPreference = "Stop"

if ($TrainingPid) {
    Stop-Process -Id $TrainingPid -Force
    "Stopped training process $TrainingPid"
    exit 0
}

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*scripts\train_yolo.py*" -and
        $_.CommandLine -notlike "*Where-Object*scripts\train_yolo.py*"
    }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
    "Stopped training process $($Process.ProcessId)"
}

if (-not $Processes) {
    "No training process is running."
}
