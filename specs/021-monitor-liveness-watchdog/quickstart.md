# Quickstart: Monitor Liveness Watchdog

**Status**: Activated; SCM recovery proof passed; D+1/D+3 observation pending.

## Preconditions

- Spec 020 runtime gate is closed.
- QA real actions are disabled and an elevated maintenance window is available.

## Static And Automated Validation

```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_monitor_liveness tests.test_reboot_safety
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py app\liveness.py tools\monitor_watchdog.py
[void][scriptblock]::Create((Get-Content tools\install_watchdog_task.ps1 -Raw))
```

## Controlled Runtime Validation

1. Run fresh, missing, malformed and stale heartbeat scenarios.
2. In QA, stop and hang the monitor separately and verify classification.
3. Verify SCM starts one replacement PID with mutex and startup guard. This
   proof passed on 2026-08-13 with the configured 60-second first restart delay.
4. Observe D+1 and D+3 for false stale alerts, duplicates or Hashcore actions.

## Evidence To Capture

- Exact tests and compilation.
- Before/after SCM failure-action export.
- Sanitized heartbeat samples.
- Watchdog open/recovery logs and delivery.
- New PID, mutex, startup guard and no-action proof.
