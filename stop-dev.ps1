<#
  停止開發環境（後端 Flask + 前端 Vite）。
  用法：powershell -ExecutionPolicy Bypass -File .\stop-dev.ps1
#>

$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root 'logs\dev-pids.json'

function Write-Ok($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Cyan }

Write-Host "`n=== 停止開發環境 ===" -ForegroundColor White

$stopped = @()
if (Test-Path $PidFile) {
    $pids = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($entry in @(@{ name = '後端'; id = $pids.backend }, @{ name = '前端'; id = $pids.frontend })) {
        if ($entry.id) {
            # /T 會一併結束子程序（例如 npm 產生的 node）
            taskkill /PID $entry.id /T /F | Out-Null
            $stopped += "$($entry.name)（PID $($entry.id)）"
        }
    }
    Remove-Item $PidFile -Force
    Write-Ok "已停止：$($stopped -join '、')"
} else {
    Write-Info "找不到 PID 檔，可能沒有透過 start-dev.ps1 啟動"
}

# 清理可能殘留的 5000 / 5173 埠占用
foreach ($port in 5000, 5173) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conn) {
        taskkill /PID $c.OwningProcess /T /F | Out-Null
        Write-Ok "已釋放 $port 埠（PID $($c.OwningProcess)）"
    }
}

Write-Host ""
