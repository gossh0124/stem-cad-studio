<#
.SYNOPSIS
    標記目前狀態為可 Demo 的穩定版本。
.DESCRIPTION
    建立 git tag (demo-wXX 格式) 並記錄摘要。
    報告前用 demo_serve.ps1 從穩定 tag 啟動展示環境。
.EXAMPLE
    .\scripts\demo_snapshot.ps1
    .\scripts\demo_snapshot.ps1 -Summary "3D assembly + schematic 完整流程"
#>
param(
    [string]$Summary = "",
    [switch]$Verified
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

# --- resolve week number ---
$now = Get-Date
$weekNum = [System.Globalization.CultureInfo]::InvariantCulture.Calendar.GetWeekOfYear(
    $now, [System.Globalization.CalendarWeekRule]::ISO8601, [DayOfWeek]::Monday
)
$baseTag = "demo-w{0:D2}" -f $weekNum

# --- find next available tag (w21, w21b, w21c ...) ---
$tag = $baseTag
$suffix = 0
while ((git -C $repoRoot tag -l $tag) -ne $null -and (git -C $repoRoot tag -l $tag) -ne "") {
    $suffix++
    $letter = [char]([int][char]'a' + $suffix)
    $tag = "${baseTag}${letter}"
}

# --- check working tree is clean ---
$status = git -C $repoRoot status --porcelain
if ($status) {
    Write-Host "[!] Working tree has uncommitted changes:" -ForegroundColor Yellow
    Write-Host $status
    $confirm = Read-Host "Continue anyway? (y/N)"
    if ($confirm -ne 'y') {
        Write-Host "Aborted." -ForegroundColor Red
        exit 1
    }
}

# --- gather stats for tag message ---
$commitHash = git -C $repoRoot rev-parse --short HEAD
$testCount  = (Get-ChildItem "$repoRoot\tests" -Recurse -Filter "test_*.py" -ErrorAction SilentlyContinue).Count
$pyCount    = (Get-ChildItem $repoRoot -Recurse -Include "*.py" -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -notmatch '[\\/](node_modules|\.venv|__pycache__)[\\/]' }).Count

$verifiedStatus = if ($Verified) { "VERIFIED (demo_verify passed)" } else { "UNVERIFIED (manual snapshot)" }

$tagMsg = @"
Demo snapshot $tag
Date: $($now.ToString("yyyy-MM-dd HH:mm"))
Commit: $commitHash
Status: $verifiedStatus
Python files: $pyCount
Test files: $testCount
Summary: $(if ($Summary) { $Summary } else { "(no summary)" })
"@

# --- create annotated tag ---
git -C $repoRoot tag -a $tag -m $tagMsg

Write-Host ""
Write-Host "=== Demo Snapshot Created ===" -ForegroundColor Green
Write-Host "Tag:    $tag"
Write-Host "Commit: $commitHash"
Write-Host "Tests:  $testCount files"
Write-Host ""
Write-Host "To demo from this snapshot later:" -ForegroundColor Cyan
Write-Host "  .\scripts\demo_serve.ps1"
Write-Host "  .\scripts\demo_serve.ps1 -Tag $tag"
