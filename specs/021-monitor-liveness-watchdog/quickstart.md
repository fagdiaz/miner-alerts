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

Use the read-only gate at the real elapsed windows. Exit code `0` means every
gate passed; exit code `2` means the window is early or evidence failed. Reports
belong under ignored `artifacts/`:

```powershell
& ".\.venv\Scripts\python.exe" tools\observe_liveness.py --stage d0 --since "2026-08-13T17:23:14-03:00" --output artifacts\spec021-d0-observation.json
& ".\.venv\Scripts\python.exe" tools\observe_liveness.py --stage d1 --since "2026-08-13T17:23:14-03:00" --output artifacts\spec021-d1-observation.json
& ".\.venv\Scripts\python.exe" tools\observe_liveness.py --stage d3 --since "2026-08-13T17:23:14-03:00" --output artifacts\spec021-d3-observation.json
```

To capture the real windows without an interactive console, install the two
one-shot SYSTEM tasks from an elevated PowerShell. They use `pythonw.exe`,
`IgnoreNew`, a five-minute execution limit and `StartWhenAvailable`:

```powershell
& ".\tools\install_liveness_observation_tasks.ps1" -RecoveryTimestamp "2026-08-13T17:23:14-03:00"
```

After both reports have been reviewed and Spec 021 is closed, remove only these
temporary capture tasks:

```powershell
& ".\tools\install_liveness_observation_tasks.ps1" -Uninstall
```

## Evidence To Capture

- Exact tests and compilation.
- Before/after SCM failure-action export.
- Sanitized heartbeat samples.
- Watchdog open/recovery logs and delivery.
- New PID, mutex, startup guard and no-action proof.
