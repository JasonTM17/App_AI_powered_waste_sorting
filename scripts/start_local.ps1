param(
  [int]$AgentPort = 8765,
  [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WebRoot = Join-Path $Root "web"

function Assert-CommandAvailable {
  param(
    [string]$Name,
    [string]$InstallHint
  )
  if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found. $InstallHint"
  }
}

function Initialize-PythonEnvironment {
  $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }

  Assert-CommandAvailable "python" "Install Python 3.10-3.12, then install uv with: python -m pip install uv"
  Write-Host "Python environment is missing; running uv sync --frozen..."
  & python -m uv sync --frozen
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
    throw "Python setup failed. Run 'python -m uv sync --frozen' from $Root and review the error."
  }
  return $venvPython
}

function Initialize-WebEnvironment {
  $nextCommand = Join-Path $WebRoot "node_modules\.bin\next.cmd"
  if (Test-Path $nextCommand) {
    return
  }

  Assert-CommandAvailable "npm.cmd" "Install Node.js 20 or newer from https://nodejs.org/."
  Write-Host "Web dependencies are missing; running npm ci..."
  Push-Location $WebRoot
  try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) {
      throw "npm ci failed with exit code $LASTEXITCODE."
    }
  } finally {
    Pop-Location
  }
  if (-not (Test-Path $nextCommand)) {
    throw "Web setup finished without Next.js. Remove web/node_modules and run 'npm ci' again."
  }
}

function Assert-RuntimeModels {
  $requiredModels = @(
    "models\best.pt",
    "models\new-class-specialist.pt"
  )
  $missingModels = @(
    $requiredModels | Where-Object { -not (Test-Path (Join-Path $Root $_)) }
  )
  if ($missingModels.Count -gt 0) {
    throw "Required runtime model(s) missing: $($missingModels -join ', '). Pull the latest main branch and verify Git completed the download."
  }
}

function Import-LocalEnvFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    return
  }
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
      return
    }
    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) {
      return
    }
    $name = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      Set-Item -Path "Env:$name" -Value $value
    }
  }
}

Import-LocalEnvFile (Join-Path $Root ".env")
Import-LocalEnvFile (Join-Path $Root ".env.local")

$AuthExplicitlyConfigured = -not [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_AUTH_DATABASE_URL) -or
  -not [string]::IsNullOrWhiteSpace($env:DATABASE_URL) -or
  -not [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_AUTH_DB) -or
  -not [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME) -or
  -not [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD)

if (-not $AuthExplicitlyConfigured -and [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_AUTH_DEV_DEFAULTS)) {
  $env:TRASH_SORTER_AUTH_DEV_DEFAULTS = "1"
}

Assert-RuntimeModels
$PythonExe = Initialize-PythonEnvironment
Initialize-WebEnvironment

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
