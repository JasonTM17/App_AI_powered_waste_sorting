[CmdletBinding()]
param(
  [string]$Namespace = "nguyenson1710",
  [string]$ArtifactRoot = "D:\trash_artifacts\dataset-parts",
  [string]$GitSha = "",
  [switch]$Push
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($GitSha)) {
  $GitSha = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
}
if ($GitSha -notmatch "^[0-9a-f]{12}$") {
  throw "GitSha must contain exactly 12 lowercase hexadecimal characters."
}

$repository = "$Namespace/trash-sorter-dataset-archive"
$manifestRoot = Join-Path $ArtifactRoot "manifests"
$workRoot = Join-Path $ArtifactRoot "dataset-v2-$GitSha-index"
$releaseManifestName = "dataset-v2-$GitSha.release-manifest.json"
$releaseManifestPath = Join-Path $workRoot $releaseManifestName
$releaseChecksumName = "$releaseManifestName.sha256"
$releaseChecksumPath = Join-Path $workRoot $releaseChecksumName
$restoreName = "RESTORE.md"
$resultPath = Join-Path $manifestRoot "dataset-v2-$GitSha.release-result.json"

function Invoke-Checked {
  param([string]$FilePath, [string[]]$Arguments)
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$FilePath failed with exit code $LASTEXITCODE"
  }
}

function Invoke-DockerRegistryCommand {
  param([string[]]$Arguments, [int]$MaxAttempts = 3)
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    & docker @Arguments
    if ($LASTEXITCODE -eq 0) { return }
    if ($attempt -eq $MaxAttempts) {
      throw "docker $($Arguments[0]) failed after $MaxAttempts attempts"
    }
    $delaySeconds = 10 * [Math]::Pow(2, $attempt - 1)
    Write-Warning "Docker registry command failed (attempt $attempt/$MaxAttempts); retrying in $delaySeconds seconds."
    Start-Sleep -Seconds $delaySeconds
  }
}

function Remove-WorkDirectory {
  if (-not (Test-Path -LiteralPath $workRoot)) { return }
  $resolvedRoot = [IO.Path]::GetFullPath($ArtifactRoot).TrimEnd("\") + "\"
  $resolvedWork = [IO.Path]::GetFullPath($workRoot)
  if (-not $resolvedWork.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove path outside artifact root: $resolvedWork"
  }
  Remove-Item -LiteralPath $resolvedWork -Recurse -Force
}

if (-not (Test-Path -LiteralPath $manifestRoot -PathType Container)) {
  throw "Dataset part manifest directory not found: $manifestRoot"
}

$manifestFiles = @(
  Get-ChildItem -LiteralPath $manifestRoot -File -Filter "dataset-v2-$GitSha-part*.manifest.json" |
    Sort-Object Name
)
$parts = @($manifestFiles | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json })
if ($parts.Count -ne 10) {
  throw "Expected 10 verified part manifests for $GitSha, found $($parts.Count)."
}

$partNumbers = @($parts | ForEach-Object { [int]$_.part } | Sort-Object)
if (($partNumbers -join ",") -ne ((1..10) -join ",")) {
  throw "Part manifests must contain each part number from 1 through 10 exactly once."
}
foreach ($part in $parts) {
  if ($part.git_commit -ne $GitSha -or [int]$part.part_count -ne 10) {
    throw "Part $($part.part) has inconsistent release metadata."
  }
  if ($part.sha256 -notmatch "^[0-9a-f]{64}$") {
    throw "Part $($part.part) has an invalid archive checksum."
  }
  if ($part.remote_digest -notmatch "^sha256:[0-9a-f]{64}$") {
    throw "Part $($part.part) is not pull-back verified or lacks a remote digest."
  }
}

Remove-WorkDirectory
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
$releaseManifest = [ordered]@{
  schema_version = 1
  release = "dataset-v2-$GitSha"
  git_commit = $GitSha
  source_repository = "https://github.com/JasonTM17/App_AI_powered_waste_sorting"
  image_repository = "docker.io/$repository"
  part_count = 10
  total_archive_bytes = [long](($parts | Measure-Object -Property archive_bytes -Sum).Sum)
  excluded = @("*.db", "*.sqlite", "*.sqlite3", "*.log", ".env*", "config.json")
  parts = @($parts | Sort-Object part)
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
}
[IO.File]::WriteAllText(
  $releaseManifestPath,
  (($releaseManifest | ConvertTo-Json -Depth 10) + "`n"),
  [Text.UTF8Encoding]::new($false)
)
$releaseHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseManifestPath).Hash.ToLowerInvariant()
[IO.File]::WriteAllText(
  $releaseChecksumPath,
  "$releaseHash  $releaseManifestName`n",
  [Text.UTF8Encoding]::new($false)
)

$restore = @"
# Trash Sorter dataset archive $GitSha

This index image contains metadata only. Dataset payloads are stored in ten immutable part images:

````text
docker.io/${repository}:${GitSha}-part01
...
docker.io/${repository}:${GitSha}-part10
````

For every part, create a container, copy `/artifacts/dataset/` to the host, and verify the bundled
`.sha256` file before extracting the `.tar.zst` archive into the same restore destination. Do not
concatenate the archives: each part is an independent tar archive rooted at `dataset_v2/`.
"@
[IO.File]::WriteAllText((Join-Path $workRoot $restoreName), $restore, [Text.UTF8Encoding]::new($false))

$dockerfile = @"
FROM alpine:3.20
LABEL org.opencontainers.image.title="Trash Sorter dataset archive index" \
      org.opencontainers.image.description="Verified ten-part dataset archive release metadata" \
      org.opencontainers.image.source="https://github.com/JasonTM17/App_AI_powered_waste_sorting" \
      org.opencontainers.image.revision="$GitSha"
WORKDIR /artifacts/dataset
COPY ["$releaseManifestName", "./$releaseManifestName"]
COPY ["$releaseChecksumName", "./$releaseChecksumName"]
COPY ["$restoreName", "./$restoreName"]
RUN sha256sum -c "$releaseChecksumName"
CMD ["sh", "-c", "cat /artifacts/dataset/RESTORE.md"]
"@
[IO.File]::WriteAllText((Join-Path $workRoot "Dockerfile"), $dockerfile, [Text.UTF8Encoding]::new($false))

$shaTag = "${repository}:${GitSha}"
$latestTag = "${repository}:latest"
Invoke-Checked "docker" @("build", "--pull", "-t", $shaTag, $workRoot)
Invoke-Checked "docker" @(
  "run", "--rm", "--entrypoint", "sh", $shaTag, "-c",
  "cd /artifacts/dataset && sha256sum -c '$releaseChecksumName'"
)

$remoteDigest = $null
if ($Push) {
  Invoke-DockerRegistryCommand @("push", $shaTag)
  $inspection = (& docker buildx imagetools inspect $shaTag 2>&1 | Out-String)
  if ($LASTEXITCODE -ne 0 -or $inspection -notmatch "Digest:\s+(sha256:[0-9a-f]{64})") {
    throw "Remote digest verification failed for $shaTag"
  }
  $remoteDigest = $Matches[1]
  Invoke-Checked "docker" @("image", "rm", "-f", $shaTag)
  Invoke-DockerRegistryCommand @("pull", $shaTag)
  Invoke-Checked "docker" @(
    "run", "--rm", "--entrypoint", "sh", $shaTag, "-c",
    "cd /artifacts/dataset && sha256sum -c '$releaseChecksumName'"
  )
  Invoke-Checked "docker" @("tag", $shaTag, $latestTag)
  Invoke-DockerRegistryCommand @("push", $latestTag)
  $latestInspection = (& docker buildx imagetools inspect $latestTag 2>&1 | Out-String)
  if ($LASTEXITCODE -ne 0 -or $latestInspection -notmatch "Digest:\s+$([regex]::Escape($remoteDigest))") {
    throw "Latest tag does not match the verified release digest."
  }
}

$result = [ordered]@{
  schema_version = 1
  git_commit = $GitSha
  release_tag = $shaTag
  latest_tag = if ($Push) { $latestTag } else { $null }
  remote_digest = $remoteDigest
  release_manifest = $releaseManifestName
  release_manifest_sha256 = $releaseHash
  part_count = 10
  total_archive_bytes = $releaseManifest.total_archive_bytes
  verified_at = if ($Push) { (Get-Date).ToUniversalTime().ToString("o") } else { $null }
}
[IO.File]::WriteAllText(
  $resultPath,
  (($result | ConvertTo-Json -Depth 5) + "`n"),
  [Text.UTF8Encoding]::new($false)
)
Copy-Item -LiteralPath $releaseManifestPath -Destination (Join-Path $manifestRoot $releaseManifestName) -Force

if ($Push) {
  Invoke-Checked "docker" @("image", "rm", "-f", $shaTag, $latestTag)
  Invoke-Checked "docker" @("builder", "prune", "-af")
}
Remove-WorkDirectory
Write-Host "Dataset archive index ready: $shaTag $remoteDigest"
