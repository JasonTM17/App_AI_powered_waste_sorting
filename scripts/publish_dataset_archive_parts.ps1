[CmdletBinding()]
param(
  [string]$Namespace = "nguyenson1710",
  [string]$ArtifactRoot = "D:\trash_artifacts\dataset-parts",
  [int]$StartPart = 1,
  [int]$EndPart = 10,
  [switch]$Push
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$datasetRoot = Join-Path $repoRoot "dataset_v2"
$gitSha = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
$repository = "$Namespace/trash-sorter-dataset-archive"
$manifestRoot = Join-Path $ArtifactRoot "manifests"

if (-not (Test-Path -LiteralPath $datasetRoot -PathType Container)) {
  throw "Dataset directory not found: $datasetRoot"
}
New-Item -ItemType Directory -Force -Path $ArtifactRoot, $manifestRoot | Out-Null

$parts = @(
  @{ Slug = "classifiers"; Paths = @(
      "kaggle_three_bin_classifier_v1",
      "kaggle_three_bin_classifier_v2",
      "kaggle_three_bin_classifier_v3_3kelas_fullcrops",
      "kaggle_three_bin_classifier_v3_with_3kelas",
      "manual_camera_capture",
      "quarantine",
      "recovered_camera_truth_20260619"
    ); RootFiles = $true },
  @{ Slug = "low-conf-queue"; Paths = @("low_conf_queue") },
  @{ Slug = "camera-anchor"; Paths = @("yolo_camera_anchor_recovery_v3", "yolo_camera_anchor_recovery_v4") },
  @{ Slug = "camera-truth"; Paths = @("yolo_camera_truth_retrain_20260619") },
  @{ Slug = "can-bottle"; Paths = @("yolo_can_bottle_recovery_v6") },
  @{ Slug = "fast-common"; Paths = @("yolo_fast_common") },
  @{ Slug = "fast-pen"; Paths = @("yolo_fast_pen") },
  @{ Slug = "kaggle-real"; Paths = @("yolo_kaggle_real_image_v5") },
  @{ Slug = "balanced-strong"; Paths = @(
      "yolo_learn_now_micro",
      "yolo_real_camera_balanced_20260619",
      "yolo_real_camera_balanced_20260619_v2",
      "yolo_strong_vietnam_common_v1"
    ) },
  @{ Slug = "trainset-weak"; Paths = @("yolo_trainset", "yolo_weak_recovery_v1", "yolo_weak_recovery_v2") }
)

function Invoke-Checked {
  param([string]$FilePath, [string[]]$Arguments)
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$FilePath failed with exit code $LASTEXITCODE"
  }
}

function Remove-WorkDirectory {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $resolvedRoot = [IO.Path]::GetFullPath($ArtifactRoot).TrimEnd("\") + "\"
  $resolvedPath = [IO.Path]::GetFullPath($Path)
  if (-not $resolvedPath.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove path outside artifact root: $resolvedPath"
  }
  Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

function New-PartArchive {
  param([hashtable]$Part, [string]$ArchivePath)
  $tarPaths = @($Part.Paths | ForEach-Object { "dataset_v2/$($_)" })
  if ($Part.RootFiles) {
    $rootFiles = Get-ChildItem -LiteralPath $datasetRoot -File |
      Where-Object {
        $_.Name -notmatch "(?i)(^\.env|\.db$|\.sqlite3?$|\.log$|^config\.json$)"
      } |
      ForEach-Object { "dataset_v2/$($_.Name)" }
    $tarPaths += $rootFiles
  }
  $tarArgs = @(
    "--zstd", "-cf", $ArchivePath,
    "--exclude=*.db", "--exclude=*.sqlite", "--exclude=*.sqlite3",
    "--exclude=*.log", "--exclude=.env*", "-C", $repoRoot
  ) + $tarPaths
  Invoke-Checked -FilePath "tar.exe" -Arguments $tarArgs
}

function Publish-Part {
  param([int]$Number, [hashtable]$Part)
  $partId = "part{0:D2}" -f $Number
  $name = "dataset-v2-$gitSha-$partId-$($Part.Slug)"
  $work = Join-Path $ArtifactRoot $name
  Remove-WorkDirectory -Path $work
  New-Item -ItemType Directory -Force -Path $work | Out-Null

  $archiveName = "$name.tar.zst"
  $archivePath = Join-Path $work $archiveName
  Write-Host "[$partId] Creating $archiveName"
  New-PartArchive -Part $Part -ArchivePath $archivePath

  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
  [IO.File]::WriteAllText(
    (Join-Path $work "$archiveName.sha256"),
    "$hash  $archiveName`n",
    [Text.UTF8Encoding]::new($false)
  )
  $manifest = [ordered]@{
    schema_version = 1
    git_commit = $gitSha
    part = $Number
    part_count = $parts.Count
    slug = $Part.Slug
    paths = @($Part.Paths)
    includes_root_metadata = [bool]$Part.RootFiles
    archive = $archiveName
    archive_bytes = (Get-Item -LiteralPath $archivePath).Length
    sha256 = $hash
    excluded = @("*.db", "*.sqlite", "*.sqlite3", "*.log", ".env*", "config.json")
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
  }
  $manifestPath = Join-Path $work "$name.manifest.json"
  $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
  Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $manifestRoot "$name.manifest.json") -Force

  $dockerfile = @"
FROM alpine:3.20
WORKDIR /artifacts/dataset
COPY ["$archiveName", "./$archiveName"]
COPY ["$archiveName.sha256", "./$archiveName.sha256"]
COPY ["$name.manifest.json", "./$name.manifest.json"]
RUN sha256sum -c "$archiveName.sha256"
CMD ["sh", "-c", "printf '%s\n' 'Dataset archive $partId/$($parts.Count).' 'Copy all part archives from their images, verify each .sha256 file, concatenate only if your restore tooling requires it, then extract every archive at the same destination root.'"]
"@
  $dockerfile | Set-Content -LiteralPath (Join-Path $work "Dockerfile") -Encoding utf8

  $shaTag = "${repository}:${gitSha}-${partId}"
  $latestTag = "${repository}:latest-${partId}"
  Invoke-Checked "docker" @("build", "--pull", "-t", $shaTag, $work)
  Invoke-Checked "docker" @(
    "run", "--rm", "--entrypoint", "sh", $shaTag, "-c",
    "cd /artifacts/dataset && sha256sum -c '$archiveName.sha256'"
  )

  if ($Push) {
    Invoke-Checked "docker" @("push", $shaTag)
    $inspection = (& docker buildx imagetools inspect $shaTag 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $inspection -notmatch "Digest:\s+(sha256:[0-9a-f]{64})") {
      throw "Remote digest verification failed for $shaTag"
    }
    $remoteDigest = $Matches[1]
    Invoke-Checked "docker" @("image", "rm", "-f", $shaTag)
    Invoke-Checked "docker" @("pull", $shaTag)
    Invoke-Checked "docker" @(
      "run", "--rm", "--entrypoint", "sh", $shaTag, "-c",
      "cd /artifacts/dataset && sha256sum -c '$archiveName.sha256'"
    )
    Invoke-Checked "docker" @("tag", $shaTag, $latestTag)
    Invoke-Checked "docker" @("push", $latestTag)
    $manifest.remote_digest = $remoteDigest
    $manifest | ConvertTo-Json -Depth 6 |
      Set-Content -LiteralPath (Join-Path $manifestRoot "$name.manifest.json") -Encoding utf8
  }

  $removeTags = @($shaTag)
  if ($Push) { $removeTags += $latestTag }
  Invoke-Checked "docker" (@("image", "rm", "-f") + $removeTags)
  Invoke-Checked "docker" @("builder", "prune", "-af")
  Remove-WorkDirectory -Path $work
}

$first = [Math]::Max(1, $StartPart)
$last = [Math]::Min($parts.Count, $EndPart)
for ($index = $first; $index -le $last; $index++) {
  Publish-Part -Number $index -Part $parts[$index - 1]
}

Write-Host "Completed dataset archive parts $first through $last for commit $gitSha."
