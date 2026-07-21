# Quickstart: Vnish Operations Automation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\event_store.py app\vnish_logs.py tools\vnish_log_collector.py
& ".\tools\install_vnish_collector_task.ps1" -WhatIf
```

Final rollout only:

```powershell
& ".\tools\install_vnish_collector_task.ps1" -IntervalMinutes 15
Start-ScheduledTask -TaskName "MinerAlertsVnishCollector"
```
