param(
  [switch]$Apply,
  [switch]$IncludeDependencies,
  [switch]$IncludeDist
)

$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Assert-WorkspacePath {
  param([string]$Path)

  $fullPath = [System.IO.Path]::GetFullPath($Path)
  $rootPrefix = $Root.TrimEnd('\') + '\'
  if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean path outside workspace: $fullPath"
  }
  return $fullPath
}

function Remove-WorkspaceItem {
  param([string]$RelativePath)

  $target = Assert-WorkspacePath (Join-Path $Root $RelativePath)
  if (-not (Test-Path -LiteralPath $target)) {
    return
  }

  if (-not $Apply) {
    Write-Host "[preview] $RelativePath"
    return
  }

  Remove-Item -LiteralPath $target -Recurse -Force
  Write-Host "[removed] $RelativePath"
}

function Remove-WorkspacePattern {
  param(
    [string]$RelativeDirectory,
    [string[]]$Patterns
  )

  $directory = Assert-WorkspacePath (Join-Path $Root $RelativeDirectory)
  if (-not (Test-Path -LiteralPath $directory)) {
    return
  }

  foreach ($pattern in $Patterns) {
    Get-ChildItem -LiteralPath $directory -File -Filter $pattern -ErrorAction SilentlyContinue |
      ForEach-Object {
        $target = Assert-WorkspacePath $_.FullName
        $display = Join-Path $RelativeDirectory $_.Name
        if (-not $Apply) {
          Write-Host "[preview] $display"
          return
        }
        Remove-Item -LiteralPath $target -Force
        Write-Host "[removed] $display"
      }
  }
}

$generatedDirectories = @(
  ".mypy_cache",
  ".omc",
  ".pytest_cache",
  ".ruff_cache",
  ".tmp",
  ".uv-cache",
  "app\__pycache__",
  "app\agent\__pycache__",
  "app\core\__pycache__",
  "app\ui\__pycache__",
  "app\ui\pages\__pycache__",
  "app\ui\widgets\__pycache__",
  "app\utils\__pycache__",
  "audit_artifacts",
  "audit_screenshots",
  "build",
  "docs\audit",
  "docs\superpowers",
  "logs",
  "runtime",
  "scripts\__pycache__",
  "tests\__pycache__",
  "tests\integration\__pycache__",
  "tests\ui\__pycache__",
  "tests\unit\__pycache__",
  "web\.audit-tmp",
  "web\.next",
  "web\.omc",
  "web\.playwright-tmp",
  "web\playwright-report",
  "web\test-results"
)

$auditGeneratedDirectories = @(
  "audit\app-ui",
  "audit\app-ui-after",
  "audit\browser-manual",
  "audit\data",
  "audit\hardware",
  "audit\output",
  "audit\screenshots",
  "audit\session"
)

$rootScratchFiles = @(
  ".codex-agent.log",
  ".coverage",
  "Trash Sorter Pro.lnk",
  "TrashSorterPro.spec",
  "build.log",
  "build4.log",
  "build5.log",
  "camera-live-frame.jpg",
  "capture_loop.py",
  "capture_loop_15m.py",
  "capture_loop_usb.py",
  "clean_queue.py",
  "fix_dataset.py",
  "grid.jpg",
  "label_grid.py",
  "predict_unlabeled.py",
  "promote_anchors.py",
  "scripts\refactor_dashboard.py",
  "stitch_grid.py",
  "test_can.jpg",
  "tmp.json",
  "tmp.txt",
  "tmp_playwright_auth.db",
  "user-dashboard-logged-in.png"
)

$webScratchFiles = @(
  ".codex-web.log",
  "ORIGINAL_REQUEST.md",
  "PROJECT.md",
  "diff.txt",
  "extract_strings.js",
  "lighthouse-report.json",
  "out.txt",
  "search.js",
  "search_diacritics.js",
  "tsconfig.tsbuildinfo"
)

Write-Host "Trash Sorter Pro workspace cleanup"
Write-Host "Root: $Root"
Write-Host "Mode: $(if ($Apply) { 'apply' } else { 'preview' })"
Write-Host ""
Write-Host "Protected: .env.local, config.json, dataset_v2, models, runs, reports"

foreach ($path in $generatedDirectories + $auditGeneratedDirectories + $rootScratchFiles) {
  Remove-WorkspaceItem $path
}

foreach ($path in $webScratchFiles) {
  Remove-WorkspaceItem (Join-Path "web" $path)
}

Remove-WorkspaceItem "audit\polling-agent-fetch.patch"
Remove-WorkspaceItem "audit\yolo-quality-20260612.json"
Remove-WorkspacePattern "web" @("audit-*.png", "map-test-*.png", "plan-*.png")

if ($IncludeDependencies) {
  Remove-WorkspaceItem ".venv"
  Remove-WorkspaceItem "web\node_modules"
}

if ($IncludeDist) {
  Remove-WorkspaceItem "dist"
}

Write-Host ""
if ($Apply) {
  Write-Host "Cleanup complete."
} else {
  Write-Host "Preview complete. Re-run with -Apply to remove listed artifacts."
}
