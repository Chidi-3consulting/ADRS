# ADRS local dev — MySQL via Docker (adrs-mysql-host :3306), app on port 8200 (localhost + LAN).
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Port = 8200

Write-Host "Checking MySQL container..." -ForegroundColor Cyan
if (-not (docker ps -q --filter "name=adrs-mysql-host" 2>$null)) {
    Write-Host "Start your MySQL container first (adrs-mysql-host on port 3306)." -ForegroundColor Red
    exit 1
}

function Get-LanIp {
    $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.InterfaceAlias -notmatch 'Loopback|Docker|vEthernet|WSL' -and
            $_.IPAddress -notmatch '^169\.254\.'
        } |
        Select-Object -ExpandProperty IPAddress
    if ($addrs) { return ($addrs | Select-Object -First 1) }
    return '127.0.0.1'
}

$LanIp = Get-LanIp
$AppUrl = "http://${LanIp}:${Port}"
$ConfigPath = Join-Path $Root "src\config\config.local.php"

if (Test-Path $ConfigPath) {
    $cfg = Get-Content $ConfigPath -Raw
    if ($cfg -match "define\s*\(\s*'APP_URL'\s*,") {
        $cfg = $cfg -replace "define\s*\(\s*'APP_URL'\s*,\s*'[^']*'\s*\)", "define('APP_URL', '$AppUrl')"
    } else {
        $cfg = $cfg.TrimEnd() + "`ndefine('APP_URL', '$AppUrl');`n"
    }
    Set-Content -Path $ConfigPath -Value $cfg -NoNewline
    Write-Host "Updated APP_URL in config.local.php -> $AppUrl" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Starting ADRS on port $Port (all interfaces)" -ForegroundColor Green
Write-Host "  Local:  http://localhost:${Port}/" -ForegroundColor Yellow
Write-Host "  LAN:    $AppUrl/" -ForegroundColor Yellow
Write-Host "  Register: $AppUrl/register" -ForegroundColor Yellow
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""
Set-Location $Root
php -S "0.0.0.0:${Port}" index.php
