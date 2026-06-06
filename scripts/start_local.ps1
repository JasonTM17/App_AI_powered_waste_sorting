param(
  [int]$AgentPort = 8765,
  [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WebRoot = Join-Path $Root "web"
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
  $PythonExe = "python"
}

function Test-PortBusy {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  return $null -ne $conn
}

function Get-PortOwnerPid {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -eq $conn) {
    return $null
  }
  return [int]$conn.OwningProcess
}

function Wait-Http {
  param([string]$Url, [int]$Seconds = 20)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $res = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($res.StatusCode -lt 500) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Get-RepoAgentProcesses {
  $rootText = [Regex]::Escape([string]$Root)
  $candidates = Get-CimInstance Win32_Process |
    Where-Object {
      $_.CommandLine -and
      $_.CommandLine -match "scripts[/\\]run_agent\.py"
    }
  foreach ($proc in $candidates) {
    if ($proc.CommandLine -match $rootText) {
      Write-Output $proc
      continue
    }

    $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    if ($null -ne $parent -and $parent.CommandLine -and $parent.CommandLine -match $rootText) {
      Write-Output $proc
    }
  }
}

function Stop-RepoAgents {
  param([object[]]$Processes)
  foreach ($proc in $Processes) {
    try {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
      Write-Host "Stopped duplicate agent PID $($proc.ProcessId)"
    } catch {
      Write-Host "Could not stop agent PID $($proc.ProcessId): $($_.Exception.Message)"
    }
  }
  Start-Sleep -Milliseconds 800
}

function Test-SameProcessFamily {
  param([int]$LeftPid, [int]$RightPid)
  if ($LeftPid -eq $RightPid) {
    return $true
  }

  $currentProcessId = $LeftPid
  while ($currentProcessId -gt 0) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
      break
    }
    if ([int]$proc.ParentProcessId -eq $RightPid) {
      return $true
    }
    $currentProcessId = [int]$proc.ParentProcessId
  }

  $currentProcessId = $RightPid
  while ($currentProcessId -gt 0) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
      break
    }
    if ([int]$proc.ParentProcessId -eq $LeftPid) {
      return $true
    }
    $currentProcessId = [int]$proc.ParentProcessId
  }

  return $false
}

Write-Host "Trash Sorter Pro local stack"
Write-Host "Root: $Root"

$repoAgents = @(Get-RepoAgentProcesses)
$agentOwnerPid = Get-PortOwnerPid $AgentPort
if ($null -ne $agentOwnerPid) {
  $ownerIsRepoAgent = $repoAgents | Where-Object { $_.ProcessId -eq $agentOwnerPid } | Select-Object -First 1
  if ($null -ne $ownerIsRepoAgent) {
    $staleAgents = @(
      $repoAgents | Where-Object {
        -not (Test-SameProcessFamily -LeftPid ([int]$_.ProcessId) -RightPid $agentOwnerPid)
      }
    )
    if ($staleAgents.Count -gt 0) {
      Write-Host "Found $($staleAgents.Count) stale repo agent process(es); stopping them to release COM locks."
      Stop-RepoAgents $staleAgents
    }
    Write-Host "Agent port $AgentPort already has a repo listener PID $agentOwnerPid; keeping it running."
  } else {
    Write-Host "Agent port $AgentPort is busy by PID $agentOwnerPid; not starting another agent."
  }
} else {
  if ($repoAgents.Count -gt 0) {
    Write-Host "Found $($repoAgents.Count) repo agent process(es) without port listener; stopping them to release COM locks."
    Stop-RepoAgents $repoAgents
  }
  Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @("scripts/run_agent.py") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden
  Write-Host "Started agent on http://127.0.0.1:$AgentPort"
}

if (Test-PortBusy $WebPort) {
  Write-Host "Web port $WebPort already has a listener; keeping it running."
} else {
  $webArgs = if ($WebPort -eq 3000) {
    @("run", "dev")
  } else {
    @("exec", "--", "next", "dev", "--hostname", "127.0.0.1", "--port", "$WebPort")
  }
  Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList $webArgs `
    -WorkingDirectory $WebRoot `
    -WindowStyle Hidden
  Write-Host "Started web on http://127.0.0.1:$WebPort"
}

$agentOk = Wait-Http "http://127.0.0.1:$AgentPort/api/health"
$webOk = Wait-Http "http://127.0.0.1:$WebPort"
$agentText = if ($agentOk) { "OK" } else { "not ready yet" }
$webText = if ($webOk) { "OK" } else { "not ready yet" }

Write-Host ""
Write-Host "Agent: http://127.0.0.1:$AgentPort $agentText"
Write-Host "Web:   http://127.0.0.1:$WebPort $webText"
Write-Host "USB camera rule: no external USB camera means black preview and camera source stays empty."
