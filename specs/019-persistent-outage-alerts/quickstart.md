# Quickstart: Persistent Outage Alerts

## Static Validation

```powershell
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py
& ".\.venv\Scripts\python.exe" -m unittest tests.test_notification_stability tests.test_vnish_scheduler
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
Get-Content app\config.example.json -Raw | ConvertFrom-Json | Out-Null
[void][scriptblock]::Create((Get-Content tools\install_vnish_collector_task.ps1 -Raw))
```

## QA Behavior

1. Force one miner OFFLINE and confirm no state message is sent before the coalescing deadline.
2. Add another affected miner inside the deadline and confirm one grouped STATE CHANGE message.
3. Advance the coordinator clock through 15 and 45 minutes and confirm grouped persistent reminders.
4. Recover a miner and confirm subsequent reminders exclude it.
5. Confirm QA blocks Hashcore actions exactly as before.

## Windows Runtime

1. Reinstall the Vnish collector scheduled task.
2. Verify the action executable ends in `.venv\Scripts\pythonw.exe` and contains no PowerShell executable.
3. Run the task manually and verify completion with no foreground window.
4. Restart the `MinerAlerts` service once after all validations.
5. Verify startup logs, mutex acquisition, production QA mode, and absence of Hashcore actions.
