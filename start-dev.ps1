<#
  一鍵啟動開發環境：PostgreSQL → 後端 Flask → 前端 Vite → 開啟瀏覽器。

  用法（專案根目錄）：
    powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
  或直接雙擊 start-dev.bat
#>

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root 'logs'
$PidFile = Join-Path $LogDir 'dev-pids.json'

$BackendPort = 5000
$FrontendPort = 5173
$FrontendUrl = "http://localhost:$FrontendPort"

function Write-Ok($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  [ERR]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=== 庫存管理系統 開發環境啟動 ===" -ForegroundColor White
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- 0. 若已在執行則提示 ---
if (Test-Path $PidFile) {
    $existing = Get-Content $PidFile -Raw | ConvertFrom-Json
    $alive = $false
    foreach ($id in @($existing.backend, $existing.frontend)) {
        if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) { $alive = $true }
    }
    if ($alive) {
        Write-Info "偵測到服務可能已在執行（PID 檔：$PidFile）。"
        Write-Info "若是舊程序殘留，請先執行 stop-dev.ps1 再重跑。"
    }
}

# --- 1. PostgreSQL 服務 ---
Write-Host "`n[1/4] PostgreSQL" -ForegroundColor White
$pgService = Get-Service -Name 'postgresql-x64-18' -ErrorAction SilentlyContinue
if ($pgService) {
    if ($pgService.Status -ne 'Running') {
        Start-Service -Name 'postgresql-x64-18'
        Start-Sleep -Seconds 3
    }
    Write-Ok "服務 postgresql-x64-18 執行中（開機自動啟動：$((Get-Service postgresql-x64-18).StartType)）"
} else {
    Write-Warn "找不到 postgresql-x64-18 服務，請確認 PostgreSQL 已安裝"
}

# --- 2. 後端 ---
Write-Host "`n[2/4] 後端 Flask（127.0.0.1:$BackendPort）" -ForegroundColor White
$python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Err "找不到後端 venv：$python"
    Write-Host "請先執行： cd backend; uv venv .venv --python 3.12; uv pip install --python .venv\Scripts\python.exe -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $Root 'backend\.env'))) {
    Write-Err "缺少 backend\.env，請先執行 backend\tools\setup_database.py"
    exit 1
}

$env:FLASK_APP = 'wsgi:app'
$backendProc = Start-Process -FilePath $python `
    -ArgumentList '-m', 'flask', '--app', 'wsgi', 'run', '--port', "$BackendPort", '--no-reload' `
    -WorkingDirectory (Join-Path $Root 'backend') `
    -RedirectStandardOutput (Join-Path $LogDir 'backend.log') `
    -RedirectStandardError (Join-Path $LogDir 'backend.err.log') `
    -WindowStyle Hidden -PassThru
Write-Ok "後端已啟動（PID $($backendProc.Id)），日誌：logs\backend.log"

# --- 3. 前端 ---
Write-Host "`n[3/4] 前端 Vite（$FrontendUrl）" -ForegroundColor White
if (-not (Test-Path (Join-Path $Root 'frontend\node_modules'))) {
    Write-Warn "尚未安裝前端套件，正在執行 npm install…"
    Push-Location (Join-Path $Root 'frontend')
    npm install
    Pop-Location
}
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npm) { $npm = 'npm.cmd' }
$frontendProc = Start-Process -FilePath $npm `
    -ArgumentList 'run', 'dev' `
    -WorkingDirectory (Join-Path $Root 'frontend') `
    -RedirectStandardOutput (Join-Path $LogDir 'frontend.log') `
    -RedirectStandardError (Join-Path $LogDir 'frontend.err.log') `
    -WindowStyle Hidden -PassThru
Write-Ok "前端已啟動（PID $($frontendProc.Id)），日誌：logs\frontend.log"

@{ backend = $backendProc.Id; frontend = $frontendProc.Id } | ConvertTo-Json | Set-Content -Path $PidFile -Encoding UTF8

# --- 4. 等服務就緒並開啟瀏覽器 ---
Write-Host "`n[4/4] 等待服務就緒…" -ForegroundColor White
$backendReady = $false
$frontendReady = $false
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline -and (-not ($backendReady -and $frontendReady))) {
    if (-not $backendReady) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 3
            if ($h.ok) { $backendReady = $true; Write-Ok "後端 API 就緒" }
        } catch { }
    }
    if (-not $frontendReady) {
        try {
            $r = Invoke-WebRequest -Uri $FrontendUrl -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $frontendReady = $true; Write-Ok "前端頁面就緒" }
        } catch { }
    }
    if (-not ($backendReady -and $frontendReady)) { Start-Sleep -Milliseconds 800 }
}

if (-not $backendReady) { Write-Err "後端未在時限內就緒，請看 logs\backend.err.log" }
if (-not $frontendReady) { Write-Err "前端未在時限內就緒，請看 logs\frontend.err.log" }

if ($backendReady -and $frontendReady) {
    Start-Process $FrontendUrl
    Write-Host ""
    Write-Host "=== 已就緒，瀏覽器已開啟 $FrontendUrl ===" -ForegroundColor Green
    Write-Host "  關閉服務： powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1"
} else {
    Write-Host ""
    Write-Host "=== 部分服務未就緒，請查看 logs/ 目錄 ===" -ForegroundColor Yellow
}
Write-Host ""
