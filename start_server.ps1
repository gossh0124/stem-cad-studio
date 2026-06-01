#Requires -Version 5.1
<#
.SYNOPSIS
    Start CADHLLM Gateway Server (auto-activate .venv)
.EXAMPLE
    .\start_server.ps1
    .\start_server.ps1 -Port 9000 -Reload
#>
param(
    [int]   $Port      = 8000,
    [string]$BindHost  = "0.0.0.0",
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

# Change to script directory
Set-Location $PSScriptRoot

# Banner
Write-Host ""
Write-Host "  +==========================================+" -ForegroundColor Cyan
Write-Host "  |    CADHLLM STEM AI Server v1.0           |" -ForegroundColor Cyan
Write-Host "  |    Text-to-CAD Pipeline Gateway          |" -ForegroundColor Cyan
Write-Host "  +==========================================+" -ForegroundColor Cyan
Write-Host ""

# Check .venv python
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  [ERROR] .venv\Scripts\python.exe not found" -ForegroundColor Red
    Write-Host "  Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "    python -m venv .venv" -ForegroundColor Yellow
    Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "    pip install -r services\requirements.txt" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check required packages
Write-Host "  [1/2] Checking package installation ..." -ForegroundColor Green
$pkgCheck = & $venvPython -c "import uvicorn, fastapi; print('ok')" 2>&1
if ($pkgCheck -ne "ok") {
    Write-Host "  [ERROR] Missing required packages. Please run:" -ForegroundColor Red
    Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "    pip install -r services\requirements.txt" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Kill stale process on target port
$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object State -eq 'Listen' | Select-Object -First 1
if ($existing) {
    $proc = Get-Process -Id $existing.OwningProcess -ErrorAction SilentlyContinue
    Write-Host ("  [WARN] Port {0} occupied by PID {1} ({2}) — killing ..." -f $Port, $existing.OwningProcess, $proc.ProcessName) -ForegroundColor Yellow
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# Create required directories
@("output\state","output\bom","output\hitl","output\cad_output") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# Start server
Write-Host "  [2/2] Starting CADHLLM Gateway Server ..." -ForegroundColor Green
Write-Host ""
Write-Host ("  UI  : http://localhost:{0}/" -f $Port) -ForegroundColor White
Write-Host ("  API : http://localhost:{0}/docs" -f $Port) -ForegroundColor White
Write-Host "  DB  : output\cadhllm_jobs.db" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server" -ForegroundColor DarkGray
Write-Host "  ============================================" -ForegroundColor DarkGray
Write-Host ""

$args_list = @(
    "run_server.py",
    "--host", $BindHost,
    "--port", $Port,
    "--db",   "output\cadhllm_jobs.db",
    "--drive","$PSScriptRoot\output"
)
if ($Reload) { $args_list += "--reload" }

$env:PYTHONIOENCODING = "utf-8"
try {
    & $venvPython @args_list
} finally {
    Write-Host ""
    Write-Host "  [Server stopped]" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
}
