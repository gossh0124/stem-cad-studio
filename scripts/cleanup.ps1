<#
.SYNOPSIS
    StemAiAgentV2 project cleanup — removes generated/temp files.
.USAGE
    .\scripts\cleanup.ps1           # interactive (prompts before heavy deletes)
    .\scripts\cleanup.ps1 -Force    # no prompts
#>
param([switch]$Force)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Remove-Safe {
    param([string]$Path, [string]$Label)
    if (Test-Path $Path) {
        $item = Get-Item $Path -Force
        if ($item.PSIsContainer) {
            $size = (Get-ChildItem $Path -Recurse -Force -ErrorAction SilentlyContinue |
                     Measure-Object -Property Length -Sum).Sum
            $sizeStr = "{0:N1} MB" -f ($size / 1MB)
        } else {
            $sizeStr = "{0:N1} MB" -f ($item.Length / 1MB)
        }
        try {
            Remove-Item $Path -Recurse -Force -Confirm:$false -ErrorAction Stop
            Write-Host "[DEL] $Label ($sizeStr)" -ForegroundColor Green
        } catch {
            Write-Host "[SKIP] $Label — locked by another process" -ForegroundColor Yellow
        }
    }
}

Write-Host "`n=== StemAiAgentV2 Cleanup ===" -ForegroundColor Cyan

# 1. Junk files at root (zero-byte or temp)
Get-ChildItem $root -File -Force |
    Where-Object { $_.Length -eq 0 -and $_.Name -notmatch '^\.' -and $_.Name -ne '__init__.py' } |
    ForEach-Object { Remove-Safe $_.FullName "Zero-byte junk: $($_.Name)" }

# 2. Tool runtime state
foreach ($dir in @('.claude-flow', '.swarm')) {
    Remove-Safe (Join-Path $root $dir) "Tool state: $dir"
}

# 3. Generated databases
Get-ChildItem $root -Filter '*.db' -File -Force -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Safe $_.FullName "Database: $($_.Name)" }

# 4. Python cache
Get-ChildItem $root -Filter '__pycache__' -Directory -Recurse -Force -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Safe $_.FullName "Cache: $($_.FullName.Replace($root, ''))" }

# 5. Training checkpoints (keep final model, remove intermediates)
$checkpointDirs = Get-ChildItem (Join-Path $root 'saved_model') -Filter 'checkpoint-*' -Directory -Recurse -ErrorAction SilentlyContinue
if ($checkpointDirs) {
    $totalMB = ($checkpointDirs | ForEach-Object {
        (Get-ChildItem $_.FullName -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    } | Measure-Object -Sum).Sum / 1MB

    if (-not $Force) {
        $answer = Read-Host "Delete $($checkpointDirs.Count) training checkpoints ($([math]::Round($totalMB)) MB)? [y/N]"
        if ($answer -ne 'y') { Write-Host "[SKIP] Checkpoints kept" -ForegroundColor Yellow; $checkpointDirs = @() }
    }
    foreach ($cp in $checkpointDirs) {
        Remove-Safe $cp.FullName "Checkpoint: $($cp.Parent.Name)/$($cp.Name)"
    }
}

# 6. Output directory (generated CAD)
if (Test-Path (Join-Path $root 'output')) {
    $outSize = (Get-ChildItem (Join-Path $root 'output') -Recurse -Force -ErrorAction SilentlyContinue |
                Measure-Object -Property Length -Sum).Sum / 1MB
    if ($outSize -gt 10) {
        if (-not $Force) {
            $answer = Read-Host "Delete output/ ($([math]::Round($outSize)) MB of generated CAD)? [y/N]"
            if ($answer -ne 'y') { Write-Host "[SKIP] output/ kept" -ForegroundColor Yellow }
            else { Remove-Safe (Join-Path $root 'output') "Generated output" }
        } else {
            Remove-Safe (Join-Path $root 'output') "Generated output"
        }
    }
}

Write-Host "`n=== Cleanup complete ===" -ForegroundColor Cyan
