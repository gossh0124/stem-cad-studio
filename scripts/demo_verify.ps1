<#
.SYNOPSIS
    驗證目前系統可正常啟動，通過後才允許打 demo snapshot tag。
.DESCRIPTION
    1. 啟動後端 (port 8099，避免衝突)
    2. 等 health check 通過 (GET / 回 200)
    3. 檢查關鍵 API 端點可回應
    4. 全部通過 → 自動呼叫 demo_snapshot.ps1
    5. 失敗 → 報錯，不打 tag
.EXAMPLE
    .\scripts\demo_verify.ps1 -Summary "Phase III schematic 完整可 Demo"
    .\scripts\demo_verify.ps1 -SkipFrontend
#>
param(
    [string]$Summary = "",
    [int]$Port = 8099,
    [switch]$SkipFrontend,
    [switch]$SkipSnapshot,
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$passed = @()
$failed = @()

function Test-Check {
    param([string]$Name, [scriptblock]$Check)
    try {
        $result = & $Check
        if ($result) {
            $script:passed += $Name
            Write-Host "  [PASS] $Name" -ForegroundColor Green
            return $true
        } else {
            $script:failed += $Name
            Write-Host "  [FAIL] $Name" -ForegroundColor Red
            return $false
        }
    } catch {
        $script:failed += $Name
        Write-Host "  [FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "=== Demo Verification ===" -ForegroundColor Cyan
Write-Host "Port: $Port | Timeout: ${TimeoutSec}s"
Write-Host ""

# ── Phase 1: Static checks ──────────────────────────
Write-Host "[Phase 1] Static checks..." -ForegroundColor Cyan

Test-Check "python executable" { Test-Path $pythonExe } | Out-Null
Test-Check "run_server.py exists" { Test-Path (Join-Path $repoRoot "run_server.py") } | Out-Null
Test-Check "gateway main.py" { Test-Path (Join-Path $repoRoot "services\gateway\main.py") } | Out-Null
Test-Check "v6 index.html" {
    Test-Path (Join-Path $repoRoot "v6\index.html")
} | Out-Null
Test-Check "component registry" {
    Test-Path (Join-Path $repoRoot "data\component_datasheet_verified.json")
} | Out-Null

if ($failed.Count -gt 0) {
    Write-Host "`n[ABORT] Static checks failed. Fix before snapshot." -ForegroundColor Red
    exit 1
}

# ── Phase 2: Backend startup ────────────────────────
Write-Host "`n[Phase 2] Backend startup (port $Port)..." -ForegroundColor Cyan

$env:CADHLLM_SKIP_RAG = "1"
$serverProc = Start-Process -FilePath $pythonExe -ArgumentList "run_server.py", "--port", $Port -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden

# wait for health
$baseUrl = "http://localhost:$Port"
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$healthy = $false

Write-Host "  Waiting for backend..." -NoNewline
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    Write-Host "." -NoNewline
    try {
        $resp = Invoke-WebRequest -Uri $baseUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # server not ready yet
    }
}
Write-Host ""

if (-not $healthy) {
    $failed += "backend startup"
    Write-Host "  [FAIL] Backend did not respond within ${TimeoutSec}s" -ForegroundColor Red
    try { $serverProc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
    exit 1
}
$passed += "backend startup"
Write-Host "  [PASS] Backend responding at $baseUrl" -ForegroundColor Green

# ── Phase 3: API endpoint checks ────────────────────
Write-Host "`n[Phase 3] API endpoint checks..." -ForegroundColor Cyan

Test-Check "GET / (UI)" {
    $r = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing -TimeoutSec 5
    $r.StatusCode -eq 200
} | Out-Null

Test-Check "GET /api/v1/components" {
    $r = Invoke-WebRequest -Uri "$baseUrl/api/v1/components" -UseBasicParsing -TimeoutSec 5
    $r.StatusCode -eq 200
} | Out-Null

# ── Phase 4: Frontend static check ──────────────────
if (-not $SkipFrontend) {
    Write-Host "`n[Phase 4] Frontend checks..." -ForegroundColor Cyan

    Test-Check "node_modules exists" {
        Test-Path (Join-Path $repoRoot "v6\node_modules")
    } | Out-Null

    Test-Check "v6 package.json" {
        Test-Path (Join-Path $repoRoot "v6\package.json")
    } | Out-Null
} else {
    Write-Host "`n[Phase 4] Frontend checks skipped (-SkipFrontend)" -ForegroundColor Gray
}

# ── Cleanup: stop test server ────────────────────────
Write-Host "`n[Cleanup] Stopping test server..." -ForegroundColor Gray
try { $serverProc | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}

# ── Results ──────────────────────────────────────────
Write-Host ""
Write-Host "=== Verification Results ===" -ForegroundColor Cyan
Write-Host "  Passed: $($passed.Count)" -ForegroundColor Green
Write-Host "  Failed: $($failed.Count)" -ForegroundColor $(if ($failed.Count -eq 0) {'Green'} else {'Red'})

if ($failed.Count -gt 0) {
    Write-Host "`nFailed checks:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "`n[BLOCKED] Snapshot NOT created. Fix failures first." -ForegroundColor Red
    exit 1
}

Write-Host "`n[ALL PASS] System verified stable." -ForegroundColor Green

# ── Auto-snapshot ────────────────────────────────────
if (-not $SkipSnapshot) {
    Write-Host "`nCreating demo snapshot..." -ForegroundColor Cyan
    $snapshotArgs = @("-Verified")
    if ($Summary) { $snapshotArgs += "-Summary", $Summary }
    & (Join-Path $PSScriptRoot "demo_snapshot.ps1") @snapshotArgs
} else {
    Write-Host "(Snapshot skipped due to -SkipSnapshot)" -ForegroundColor Gray
}
