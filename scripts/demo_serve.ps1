<#
.SYNOPSIS
    從穩定的 demo tag 啟動展示環境（前端 + 後端），不影響開發中的 master。
.DESCRIPTION
    使用 git worktree 在另一個資料夾建立穩定版本的副本，
    並啟動前後端 server。結束後自動清理 worktree。
.EXAMPLE
    .\scripts\demo_serve.ps1              # 用最新的 demo-wXX tag
    .\scripts\demo_serve.ps1 -Tag demo-w21  # 指定特定 tag
    .\scripts\demo_serve.ps1 -ListTags      # 列出所有 demo tags
#>
param(
    [string]$Tag = "",
    [switch]$ListTags,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

# --- list mode ---
if ($ListTags) {
    Write-Host "=== Available Demo Snapshots ===" -ForegroundColor Cyan
    $tags = git -C $repoRoot tag -l "demo-*" --sort=-creatordate
    if (-not $tags) {
        Write-Host "(none yet - run demo_snapshot.ps1 first)" -ForegroundColor Yellow
        exit 0
    }
    foreach ($t in $tags) {
        $date = git -C $repoRoot log -1 --format="%ai" $t 2>$null
        $body = git -C $repoRoot tag -l $t -n99 --format="%(contents:body)"

        # extract status and summary
        $statusLine  = ($body -split "`n") | Where-Object { $_ -match "^Status:" }  | Select-Object -First 1
        $summaryLine = ($body -split "`n") | Where-Object { $_ -match "^Summary:" } | Select-Object -First 1

        $isVerified = $statusLine -match "VERIFIED"
        $badge = if ($isVerified) { "[VERIFIED]" } else { "[manual]" }
        $badgeColor = if ($isVerified) { "Green" } else { "Yellow" }

        Write-Host "  $t  " -NoNewline -ForegroundColor Green
        Write-Host "$badge " -NoNewline -ForegroundColor $badgeColor
        Write-Host "($date)"
        if ($summaryLine) {
            Write-Host "         $summaryLine" -ForegroundColor Gray
        }
    }
    exit 0
}

# --- resolve tag ---
if (-not $Tag) {
    $Tag = git -C $repoRoot tag -l "demo-*" --sort=-creatordate | Select-Object -First 1
    if (-not $Tag) {
        Write-Host "[ERROR] No demo tags found. Run demo_snapshot.ps1 first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using latest demo tag: $Tag" -ForegroundColor Cyan
}

# --- verify tag exists ---
$tagCheck = git -C $repoRoot tag -l $Tag
if (-not $tagCheck) {
    Write-Host "[ERROR] Tag '$Tag' not found. Use -ListTags to see available." -ForegroundColor Red
    exit 1
}

# --- show tag info ---
Write-Host ""
Write-Host "=== Demo Tag: $Tag ===" -ForegroundColor Green
git -C $repoRoot tag -l $Tag -n99 --format="%(contents)"
Write-Host ""

# --- setup worktree ---
$worktreePath = Join-Path $repoRoot ".demo-worktree"

if (Test-Path $worktreePath) {
    Write-Host "Cleaning up previous demo worktree..." -ForegroundColor Yellow
    git -C $repoRoot worktree remove $worktreePath --force 2>$null
    if (Test-Path $worktreePath) {
        Remove-Item $worktreePath -Recurse -Force -Confirm:$false
    }
}

Write-Host "Creating demo worktree at $worktreePath ..." -ForegroundColor Cyan
git -C $repoRoot worktree add $worktreePath $Tag --detach

# --- symlink gitignored runtime dependencies ---
Write-Host "Linking runtime dependencies..." -ForegroundColor Cyan

$symlinks = @(
    @{ Name = ".venv";            Src = ".venv" },
    @{ Name = "node_modules";     Src = "v6\node_modules";  Dst = "v6\node_modules" },
    @{ Name = "saved_model (weights)"; Src = "saved_model";  },
    @{ Name = "cadhllm_lora_b";   Src = "cadhllm_lora_b" },
    @{ Name = "data\rag_db";      Src = "data\rag_db" },
    @{ Name = "shells";           Src = "shells" }
)

foreach ($link in $symlinks) {
    $srcFull = Join-Path $repoRoot $link.Src
    $dstRel  = if ($link.Dst) { $link.Dst } else { $link.Src }
    $dstFull = Join-Path $worktreePath $dstRel

    if (-not (Test-Path $srcFull)) {
        Write-Host "  SKIP $($link.Name) (not found in main repo)" -ForegroundColor Gray
        continue
    }

    $dstParent = Split-Path $dstFull -Parent
    if (-not (Test-Path $dstParent)) {
        New-Item -ItemType Directory -Path $dstParent -Force | Out-Null
    }

    if (Test-Path $dstFull) {
        Write-Host "  SKIP $($link.Name) (already exists)" -ForegroundColor Gray
        continue
    }

    try {
        New-Item -ItemType SymbolicLink -Path $dstFull -Target $srcFull -ErrorAction Stop | Out-Null
        Write-Host "  OK   $($link.Name)" -ForegroundColor Green
    }
    catch {
        Write-Host "  WARN $($link.Name) - symlink failed (try running as Admin)" -ForegroundColor Yellow
        Write-Host "       Fallback: creating junction..." -ForegroundColor Yellow
        try {
            cmd /c mklink /J "`"$dstFull`"" "`"$srcFull`"" 2>$null | Out-Null
            Write-Host "  OK   $($link.Name) (junction)" -ForegroundColor Green
        }
        catch {
            Write-Host "  FAIL $($link.Name) - manual copy needed" -ForegroundColor Red
        }
    }
}

# --- ensure output dir exists ---
$outputDir = Join-Path $worktreePath "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

Write-Host ""
Write-Host "=== Demo Environment Ready ===" -ForegroundColor Green
Write-Host "Worktree: $worktreePath"
Write-Host ""

# --- verify linked dependencies ---
$venvOk     = Test-Path (Join-Path $worktreePath ".venv\Scripts\python.exe")
$nodeOk     = Test-Path (Join-Path $worktreePath "v6\node_modules")
Write-Host "Dependencies:" -ForegroundColor Cyan
Write-Host "  .venv:        $(if ($venvOk) {'OK'} else {'MISSING'})" -ForegroundColor $(if ($venvOk) {'Green'} else {'Red'})
Write-Host "  node_modules: $(if ($nodeOk) {'OK'} else {'MISSING'})" -ForegroundColor $(if ($nodeOk) {'Green'} else {'Red'})
Write-Host ""

if (-not $venvOk) {
    Write-Host "[ERROR] .venv not linked. Backend cannot start." -ForegroundColor Red
    Write-Host "  Try: New-Item -ItemType Junction -Path `"$worktreePath\.venv`" -Target `"$repoRoot\.venv`"" -ForegroundColor Yellow
    exit 1
}

Write-Host "Start servers:" -ForegroundColor Cyan
Write-Host "  Backend:  .venv\Scripts\python.exe run_server.py --port 8000"
Write-Host "  Frontend: cd v6 && npm start"
Write-Host ""

$startNow = Read-Host "Start backend + frontend? (Y/n)"
if ($startNow -eq '' -or $startNow -eq 'y' -or $startNow -eq 'Y') {

    if (-not $FrontendOnly) {
        Write-Host "Starting backend (port 8000)..." -ForegroundColor Green
        $backendCmd = "cd `"$worktreePath`"; `$env:CADHLLM_SKIP_RAG='1'; .\.venv\Scripts\python.exe run_server.py --port 8000"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    }

    if (-not $BackendOnly) {
        Start-Sleep -Seconds 2
        Write-Host "Starting frontend (port 3000)..." -ForegroundColor Green
        $frontendCmd = "cd `"$worktreePath\v6`"; npm start"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    }

    Write-Host ""
    Write-Host "=== Servers Starting ===" -ForegroundColor Green
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "When done, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\demo_cleanup.ps1"
}
