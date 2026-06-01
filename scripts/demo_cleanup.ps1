<#
.SYNOPSIS
    清理 demo worktree + 過期截圖，回到正常開發狀態。
.PARAMETER KeepWeeks
    保留最近幾週的截圖（預設 4 週）。更早的截圖資料夾自動刪除。
    JSON 指標快照永遠保留（很小，且已進 git）。
#>
param(
    [int]$KeepWeeks = 4
)

$repoRoot = Split-Path $PSScriptRoot -Parent

# --- 1. Clean worktree ---
$worktreePath = Join-Path $repoRoot ".demo-worktree"

if (Test-Path $worktreePath) {
    Write-Host "Removing demo worktree..." -ForegroundColor Yellow
    git -C $repoRoot worktree remove $worktreePath --force 2>$null
    if (Test-Path $worktreePath) {
        Remove-Item $worktreePath -Recurse -Force -Confirm:$false
    }
    Write-Host "  Worktree cleaned." -ForegroundColor Green
} else {
    Write-Host "No demo worktree found." -ForegroundColor Gray
}

# --- 2. Clean old screenshots ---
$metricsDir = Join-Path $repoRoot "docs\weekly_metrics"
if (-not (Test-Path $metricsDir)) { exit 0 }

$cutoff = (Get-Date).AddDays(-($KeepWeeks * 7)).ToString("yyyy-MM-dd")
$dirs = Get-ChildItem $metricsDir -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -lt $cutoff }

if ($dirs.Count -gt 0) {
    Write-Host ""
    Write-Host "Cleaning screenshots older than $KeepWeeks weeks ($cutoff)..." -ForegroundColor Yellow
    foreach ($d in $dirs) {
        $size = (Get-ChildItem $d.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 1)
        Remove-Item $d.FullName -Recurse -Force -Confirm:$false
        Write-Host "  Removed $($d.Name)/ ($sizeMB MB)" -ForegroundColor Gray
    }
} else {
    Write-Host "No old screenshots to clean." -ForegroundColor Gray
}

# --- 3. Summary ---
$remaining = Get-ChildItem $metricsDir -Directory -ErrorAction SilentlyContinue
$jsonCount = (Get-ChildItem $metricsDir -Filter "*.json" -ErrorAction SilentlyContinue).Count
Write-Host ""
Write-Host "Weekly metrics: $jsonCount JSON snapshots (kept forever), $($remaining.Count) screenshot folders" -ForegroundColor Cyan
