<#
  只啟動後端（單一服務模式）。

  兩種用法：
  1. 單一服務（正式／展示用）：先打包前端，Flask 同時提供 API 與網頁
       cd frontend; npm run build
       powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
     → 網址 http://127.0.0.1:5000
  2. 純 API（開發除錯）：加 -ApiOnly 參數，只啟動 API，不開瀏覽器
#>

param(
    [switch]$ApiOnly,
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root 'logs'
$Port = 5000
$PidFile = Join-Path $LogDir 'backend-pid.txt'

function Write-Ok($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg) { Write-Host "  [ERR]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=== 只啟動後端 ===" -ForegroundColor White
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# 1. PostgreSQL
Write-Host "`n[1/3] PostgreSQL" -ForegroundColor White
$pg = Get-Service -Name 'postgresql-x64-18' -ErrorAction SilentlyContinue
if ($pg) {
    if ($pg.Status -ne 'Running') { Start-Service -Name 'postgresql-x64-18'; Start-Sleep -Seconds 3 }
    Write-Ok "服務 postgresql-x64-18 執行中"
} else {
    Write-Warn "找不到 postgresql-x64-18 服務"
}

# 2. 前端打包（單一服務模式需要）
Write-Host "`n[2/3] 前端" -ForegroundColor White
$dist = Join-Path $Root 'frontend\dist\index.html'
if (-not $ApiOnly) {
    if ((-not (Test-Path $dist)) -or (-not $NoBuild)) {
        if (Test-Path (Join-Path $Root 'frontend\node_modules')) {
            Write-Info "打包前端（npm run build）…"
            Push-Location (Join-Path $Root 'frontend')
            npm run build | Out-Null
            Pop-Location
            if (Test-Path $dist) { Write-Ok "前端已打包：frontend\dist" }
            else { Write-Warn "打包失敗，後端將只提供 API" }
        } else {
            Write-Warn "尚未安裝前端套件（frontend\node_modules 不存在），請先 npm install"
        }
    } else {
        Write-Ok "沿用既有前端打包（frontend\dist）"
    }
} else {
    Write-Info "ApiOnly 模式：只啟動 API"
}

# 3. 啟動後端
Write-Host "`n[3/3] 啟動 Flask" -ForegroundColor White
$python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { Write-Err "找不到 venv：$python"; exit 1 }
if (-not (Test-Path (Join-Path $Root 'backend\.env'))) {
    Write-Err "缺少 backend\.env，請先執行 backend\tools\setup_database.py"
    exit 1
}

$env:FLASK_APP = 'wsgi:app'
$proc = Start-Process -FilePath $python `
    -ArgumentList '-m', 'flask', '--app', 'wsgi', 'run', '--port', "$Port", '--no-reload' `
    -WorkingDirectory (Join-Path $Root 'backend') `
    -RedirectStandardOutput (Join-Path $LogDir 'backend.log') `
    -RedirectStandardError (Join-Path $LogDir 'backend.err.log') `
    -WindowStyle Hidden -PassThru
$proc.Id | Set-Content -Path $PidFile -Encoding ASCII
Write-Ok "後端已啟動（PID $($proc.Id)），日誌：logs\backend.log"

# 等待就緒
$ready = $false
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline -and -not $ready) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($h.ok) { $ready = $true }
    } catch { }
    if (-not $ready) { Start-Sleep -Milliseconds 700 }
}

if ($ready) {
    Write-Ok "API 就緒：http://127.0.0.1:$Port"
    if (-not $ApiOnly -and (Test-Path $dist)) {
        Write-Ok "網頁（單一服務）：http://127.0.0.1:$Port"
        Start-Process "http://127.0.0.1:$Port"
    } elseif ($ApiOnly) {
        Write-Info "API only 模式，未開啟瀏覽器"
    }
    Write-Host ""
    Write-Host "  停止後端： powershell -ExecutionPolicy Bypass -File .\stop-backend.ps1" -ForegroundColor White
} else {
    Write-Err "後端未在時限內就緒，請看 logs\backend.err.log"
}
Write-Host ""
