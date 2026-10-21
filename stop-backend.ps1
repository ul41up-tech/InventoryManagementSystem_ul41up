<#
  停止「只啟動後端」模式啟動的 Flask 程序。
  用法：powershell -ExecutionPolicy Bypass -File .\stop-backend.ps1
#>

$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root 'logs\backend-pid.txt'

function Write-Ok($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Cyan }

Write-Host "`n=== 停止後端 ===" -ForegroundColor White

if (Test-Path $PidFile) {
    $pidValue = (Get-Content $PidFile -Raw).Trim()
    if ($pidValue) {
        taskkill /PID $pidValue /T /F | Out-Null
        Write-Ok "已停止後端（PID $pidValue）"
    }
    Remove-Item $PidFile -Force
} else {
    Write-Info "找不到 PID 檔"
}

$conn = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conn) {
    taskkill /PID $c.OwningProcess /T /F | Out-Null
    Write-Ok "已釋放 5000 埠（PID $($c.OwningProcess)）"
}
Write-Host ""
