@echo off
rem Miner Alerts - Remote UI Server (Dashboard & Metrics Sync)
rem Serves HTML Dashboard on http://192.168.100.22:8080/
cd /d "%~dp0"
title Miner Alerts UI Server (Port 8080)
echo =======================================================
echo Starting Miner Alerts Remote UI Server...
echo Access Dashboard from phone/PC: http://192.168.100.22:8080/
echo Access Grafana from phone/PC:   http://192.168.100.22:3000/
echo =======================================================
".venv\Scripts\python.exe" tools\serve_monitor_ui.py --host 0.0.0.0 --port 8080 --interval 20
pause
