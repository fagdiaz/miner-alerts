# Miner Alerts - Remote UI Server (Dashboard & Metrics Sync)
# Serves HTML Dashboard on http://192.168.100.22:8080/
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Starting Miner Alerts Remote UI Server..." -ForegroundColor Green
Write-Host "Access Dashboard from phone/PC: http://192.168.100.22:8080/" -ForegroundColor Yellow
Write-Host "Access Grafana from phone/PC:   http://192.168.100.22:3000/" -ForegroundColor Yellow
Write-Host "=======================================================" -ForegroundColor Cyan

& ".\.venv\Scripts\python.exe" tools\serve_monitor_ui.py --host 0.0.0.0 --port 8080 --interval 20
