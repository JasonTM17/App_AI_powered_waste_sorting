param(
  [int]$AgentPort = 8765,
  [string]$CloudflaredPath = "cloudflared",
  [switch]$NoAgentStart
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $Root ".env.local"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Import-LocalEnvFile {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
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
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      Set-Item -Path "Env:$name" -Value $value
    }
  }
}

function Set-LocalEnvValue {
  param([string]$Name, [string]$Value)
  $line = "$Name=$Value"
  if (-not (Test-Path -LiteralPath $EnvFile)) {
    Set-Content -LiteralPath $EnvFile -Value $line -Encoding UTF8
    return
  }
  $lines = @(Get-Content -LiteralPath $EnvFile)
  $found = $false
  $next = foreach ($existing in $lines) {
    if ($existing -match "^\s*$([Regex]::Escape($Name))=") {
      $found = $true
      $line
    } else {
      $existing
    }
  }
  if (-not $found) {
    $next += $line
  }
  Set-Content -LiteralPath $EnvFile -Value $next -Encoding UTF8
}

function Ensure-BridgeSecret {
  Import-LocalEnvFile $EnvFile
  if (-not [string]::IsNullOrWhiteSpace($env:TRASH_SORTER_HARDWARE_BRIDGE_SECRET)) {
    return
  }
  $bytes = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($bytes)
  } finally {
    $rng.Dispose()
  }
  $secret = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
  Set-LocalEnvValue "TRASH_SORTER_HARDWARE_BRIDGE_SECRET" $secret
  $env:TRASH_SORTER_HARDWARE_BRIDGE_SECRET = $secret
}

function Test-PortBusy {
  param([int]$Port)
  return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Resolve-CloudflaredExecutable {
  param([string]$Candidate)
  $command = Get-Command $Candidate -ErrorAction SilentlyContinue
  if ($null -ne $command) {
    return $command.Source
  }
  $knownPaths = @(
    (Join-Path ${env:ProgramFiles(x86)} "cloudflared\cloudflared.exe"),
    (Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"),
    (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\cloudflared.exe")
  )
  $installed = $knownPaths | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
  if ($installed) {
    return $installed
  }
  throw "cloudflared was not found. Install Cloudflare Tunnel, then rerun this script."
}

function Save-CurrentTunnelUrl {
  param([int]$WaitSeconds = 15)
  $deadline = (Get-Date).AddSeconds($WaitSeconds)
  $pattern = "https://[-a-z0-9]+\.trycloudflare\.com"
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $err) {
      $match = Select-String -Path $err -Pattern $pattern | Select-Object -Last 1
      if ($match) {
        $urlMatch = [Regex]::Match($match.Line, $pattern)
        if ($urlMatch.Success) {
          $currentUrl = $urlMatch.Value
          Set-Content -LiteralPath (Join-Path $LogDir "current-hardware-bridge-url.txt") -Value $currentUrl -Encoding UTF8
          Write-Host "Hardware bridge URL: $currentUrl"
          return
        }
      }
    }
    Start-Sleep -Milliseconds 500
  }
  Write-Warning "Tunnel started but its public URL was not found within $WaitSeconds seconds. Check $err."
}

function Get-PortOwnerPid {
  param([int]$Port)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -eq $conn) {
    return $null
  }
  return [int]$conn.OwningProcess
}

function Test-RepoAgentProcess {
  param([int]$ProcessId)
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
  if ($null -eq $proc -or [string]::IsNullOrWhiteSpace($proc.CommandLine)) {
    return $false
  }
  $rootPattern = [Regex]::Escape([string]$Root)
  if ($proc.CommandLine -notmatch "scripts[/\\]run_agent\.py") {
    return $false
  }
  if ($proc.CommandLine -match $rootPattern -or $proc.ExecutablePath -match $rootPattern) {
    return $true
  }
  $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.ParentProcessId)" -ErrorAction SilentlyContinue
  return $null -ne $parent -and $parent.CommandLine -match $rootPattern
}

function Start-Agent {
  $python = Join-Path $Root ".venv\Scripts\python.exe"
  if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
  }
  Start-Process `
    -FilePath $python `
    -ArgumentList @("scripts/run_agent.py") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden
  Start-Sleep -Seconds 5
}

function Start-SupabaseStateBridge {
  $databaseUrl = $env:TRASH_SORTER_SUPABASE_DATABASE_URL
  if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
    $databaseUrl = $env:TRASH_SORTER_AUTH_DATABASE_URL
  }
  if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
    Write-Host "Supabase state bridge not started: database URL is not configured."
    return
  }

  $rootPattern = [Regex]::Escape([string]$Root)
  $existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and
      $_.CommandLine -match "supabase_hardware_bridge\.py" -and
      $_.CommandLine -match $rootPattern
    } |
    Select-Object -First 1
  if ($null -ne $existing) {
    Write-Host "Supabase state bridge already running (PID $($existing.ProcessId))."
    return
  }

  $python = Join-Path $Root ".venv\Scripts\python.exe"
  if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
  }
  $env:TRASH_SORTER_SUPABASE_DATABASE_URL = $databaseUrl
  $env:PYTHONPATH = [string]$Root
  $syncOut = Join-Path $LogDir "supabase-hardware-bridge.out.log"
  $syncErr = Join-Path $LogDir "supabase-hardware-bridge.err.log"
  Start-Process `
    -FilePath $python `
    -ArgumentList @("scripts/supabase_hardware_bridge.py", "--interval", "2", "--history-limit", "50") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $syncOut `
    -RedirectStandardError $syncErr `
    -WindowStyle Hidden
  Write-Host "Started Supabase hardware state bridge (2-second sensor sync)."
}

Ensure-BridgeSecret

if (-not $NoAgentStart) {
  $ownerPid = Get-PortOwnerPid $AgentPort
  if ($null -ne $ownerPid) {
    if (Test-RepoAgentProcess $ownerPid) {
      Write-Host "Repo agent already running on port $AgentPort (PID $ownerPid)."
    } else {
      throw "Port $AgentPort is busy by PID $ownerPid and is not this repo agent."
    }
  } else {
    Start-Agent
  }
}

if (-not (Test-PortBusy $AgentPort)) {
  throw "Local agent is not listening on port $AgentPort."
}

$cloudflared = Resolve-CloudflaredExecutable $CloudflaredPath

Start-SupabaseStateBridge

$out = Join-Path $LogDir "public-hardware-bridge.out.log"
$err = Join-Path $LogDir "public-hardware-bridge.err.log"
$url = "http://127.0.0.1:$AgentPort"
$existingTunnel = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -eq "cloudflared.exe" -and $_.CommandLine -match [Regex]::Escape($url) } |
  Select-Object -First 1
if ($null -ne $existingTunnel) {
  Write-Host "Cloudflare Tunnel already running (PID $($existingTunnel.ProcessId))."
  Save-CurrentTunnelUrl -WaitSeconds 2
  exit 0
}
Start-Process `
  -FilePath $cloudflared `
  -ArgumentList @("tunnel", "--url", $url) `
  -WorkingDirectory $Root `
  -RedirectStandardOutput $out `
  -RedirectStandardError $err `
  -WindowStyle Hidden

Write-Host "Started Cloudflare Tunnel for $url"
Save-CurrentTunnelUrl
Write-Host "Set that URL as TRASH_SORTER_HARDWARE_BRIDGE_URL in Vercel production."
