# ADRS Python local dev — FastAPI + Jinja2, app on port 8200 (localhost + LAN).
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Port = 8200

Write-Host "Checking python dependencies..." -ForegroundColor Cyan
try {
    python -c "import fastapi, uvicorn, sqlalchemy, jinja2" 2>$null
    Write-Host "Dependencies are present." -ForegroundColor Green
} catch {
    Write-Host "Installing missing dependencies from requirements.txt..." -ForegroundColor Yellow
    pip install -r (Join-Path $Root "requirements.txt")
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

# Set environment variables for runtime configuration
$env:APP_ENV = "local"
$env:APP_URL = $AppUrl

# If docker is running and MySQL host is up, user can run:
# $env:DATABASE_URL = "mysql+pymysql://adrs_user:adrs_pass@localhost:3306/adrs_db"
# Default is SQLite local db: retention.db

Write-Host ""
Write-Host "Starting ADRS Python App on port $Port (all interfaces)" -ForegroundColor Green
Write-Host "  Local:    http://localhost:${Port}/" -ForegroundColor Yellow
Write-Host "  LAN:      $AppUrl/" -ForegroundColor Yellow
Write-Host "  Register: $AppUrl/register" -ForegroundColor Yellow
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

Set-Location $Root
python main.py
